import re
import json
import os
import requests
from bs4 import BeautifulSoup
import ftfy
from datetime import datetime
import time

from src.utils.logger import log_info, log_error

# Optional Selenium imports for dynamic page loading
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    log_info("Selenium not available. Dynamic page loading will be limited.")

try:
    from src.utils import build_graph
except ImportError:
    import src.utils.build_graph as build_graph


class MCMPScraper:
    BASE_URL = "https://www.philosophie.lmu.de"
    EVENT_SOURCES = [
        f"{BASE_URL}/mcmp/en/latest-news/events-overview/index.html",
        f"{BASE_URL}/mcmp/en/events/index.html",
        f"{BASE_URL}/mcmp/en/index.html",
    ]
    PEOPLE_URLS = [f"{BASE_URL}/mcmp/en/people/index.html"]
    RESEARCH_URL = f"{BASE_URL}/mcmp/en/research/index.html"
    FOR_STUDENTS_URL = f"{BASE_URL}/mcmp/en/for-students/"
    BACHELOR_URL = f"{BASE_URL}/en/study/degree-programs/bachelor-in-philosophy-philosophy-major/"
    MASTER_URL = f"{BASE_URL}/en/study/degree-programs/master-in-logic-and-philosophy-of-science/"

    def __init__(self):
        self.events = []
        self.people = []
        self.research = []
        self.general = []
        self.academic_offerings = []
        self._scraped_person_urls: set = set()  # O(1) dedup for _scrape_single_person_page
        self.important_urls = self.load_important_urls()

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch a page and enforce UTF-8 to prevent mojibake."""
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = "utf-8"  # Force before .text — prevents mojibake
        fixed = ftfy.fix_text(response.text)  # Repair any residual encoding issues
        return BeautifulSoup(fixed, "html.parser")

    def _clean_text(self, text):
        """Removes common navigation noise from scraped text."""
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip breadcrumbs
            if "You are in the following website hierarchy" in line or "You are here:" in line:
                continue
            if line in ["Home", "Latest news", "Events overview", "Event", "up", "Share", "To share copy", "Link", "Share on"]:
                continue
            # Skip footer links
            if line in ["Facebook", "X", "LinkedIn", "Instagram"]:
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def load_important_urls(self):
        """Loads important URLs from data/important_urls.txt."""
        urls = []
        try:
            with open("data/important_urls.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)
            log_info(f"Loaded {len(urls)} important URLs from file.")
        except FileNotFoundError:
            log_error("data/important_urls.txt not found. Using defaults.")
        return urls

    def _normalize_url(self, href, source_url):
        """Normalizes a URL to absolute form."""
        if href.startswith("http"):
            return href
        elif href.startswith("/"):
            return f"{self.BASE_URL}{href}"
        else:
            base_path = source_url.rsplit("/", 1)[0]
            return f"{base_path}/{href}".replace("/./", "/")

    def _is_event_link(self, href):
        """Checks if a URL looks like an event page."""
        if not href:
            return False
        lower_href = href.lower()
        if "/event/" in href:
            return True
        if any(kw in lower_href for kw in ["talk-", "workshop-", "conference-", "colloquium-", "seminar-", "reading-group"]):
            return ".html" in href
        return False

    # ------------------------------------------------------------------
    # Events scraping
    # ------------------------------------------------------------------

    def scrape_events(self):
        """Scrapes multiple sources for event links.

        Uses Selenium for the events-overview page (dynamic 'Load more' button).
        Falls back to static requests for all other sources.
        """
        seen_urls = set()

        events_overview_url = f"{self.BASE_URL}/mcmp/en/latest-news/events-overview/index.html"

        if SELENIUM_AVAILABLE:
            log_info(f"Using Selenium to scrape {events_overview_url} (dynamic loading)")
            try:
                event_links = self._fetch_events_with_selenium(events_overview_url)
                for url, title in event_links:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        self.events.append({
                            "title": title,
                            "url": url,
                            "scraped_at": datetime.now().isoformat(),
                        })
                log_info(f"Selenium found {len(self.events)} events from events-overview")
            except Exception as e:
                log_error(f"Selenium failed, falling back to static scraping: {e}")

        for source_url in self.EVENT_SOURCES:
            # Skip events-overview if already scraped with Selenium
            if "events-overview" in source_url and SELENIUM_AVAILABLE and len(self.events) > 0:
                continue

            log_info(f"Starting static scrape of {source_url}")
            try:
                soup = self._fetch_page(source_url)

                event_links = soup.select("a.filterable-list__list-item-link.is-events")

                if not event_links:
                    event_links = [
                        link for link in soup.find_all("a", href=True)
                        if self._is_event_link(link["href"])
                    ]

                for link in event_links:
                    href = link.get("href", "")
                    text = link.get_text(strip=True)
                    full_url = self._normalize_url(href, source_url)

                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    title = text or href.split("/")[-1].replace(".html", "").replace("-", " ").title()
                    self.events.append({
                        "title": title,
                        "url": full_url,
                        "scraped_at": datetime.now().isoformat(),
                    })

            except Exception as e:
                log_error(f"Error scraping {source_url}: {e}")

        log_info(f"Found {len(self.events)} unique event links in total.")

        for i, event in enumerate(self.events):
            log_info(f"Scraping event {i+1}/{len(self.events)}: {event['title']}")
            self.scrape_event_details(event)

        return self.events

    def _fetch_events_with_selenium(self, url):
        """Uses Selenium to load all events from a page with 'Load more' button.

        Returns list of (url, title) tuples.
        """
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        driver = None
        event_links = []

        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=chrome_options,
            )
            driver.get(url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.filterable-list__list-item-link.is-events"))
            )

            max_clicks = 10
            clicks = 0
            while clicks < max_clicks:
                try:
                    load_more_btn = driver.find_element(By.CSS_SELECTOR, "button.filterable-list__load-more")
                    if load_more_btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView();", load_more_btn)
                        driver.execute_script("arguments[0].click();", load_more_btn)
                        time.sleep(1)
                        clicks += 1
                        log_info(f"Clicked 'Load more' button ({clicks} times)")
                    else:
                        break
                except (NoSuchElementException, TimeoutException):
                    break

            links = driver.find_elements(By.CSS_SELECTOR, "a.filterable-list__list-item-link.is-events")
            for link in links:
                try:
                    href = link.get_attribute("href")
                    title = link.text.strip()
                    if href:
                        event_links.append((href, title))
                except Exception:
                    pass

            log_info(f"Selenium extracted {len(event_links)} event links")

        finally:
            if driver:
                driver.quit()

        return event_links

    def scrape_event_details(self, event):
        """Scrapes details for a single event with structured field extraction."""
        try:
            soup = self._fetch_page(event["url"])

            metadata = {}

            # Extract speaker from main H1 (e.g., "Talk: Simon Saunders (Oxford)")
            h1 = soup.find("h1")
            if h1:
                speaker_text = h1.get_text(strip=True)
                if ":" in speaker_text:
                    metadata["speaker"] = speaker_text.split(":", 1)[1].strip()

            # Extract labeled sections (Title, Abstract, Date)
            for h2 in soup.find_all("h2"):
                label = h2.get_text(strip=True).rstrip(":").lower()

                if label == "title":
                    event["talk_title"] = self._extract_section_content(h2)
                elif label == "abstract":
                    event["abstract"] = self._extract_section_content(h2)
                elif label == "date":
                    date_text = self._extract_section_content(h2)
                    metadata.update(self._parse_date_time(date_text))

            # Extract location from address tag (most reliable)
            address = soup.find("address")
            if address:
                metadata["location"] = " ".join(address.get_text(" ", strip=True).split())

            # Fallback: Try dl/dt/dd structure for any missing metadata
            for dl in soup.find_all("dl"):
                for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                    key = dt.get_text(strip=True).lower().replace(":", "")
                    val = dd.get_text(" ", strip=True)
                    if key and val and key not in metadata:
                        metadata[key] = val

            event["metadata"] = metadata

            # Build description from abstract + title
            desc_parts = []
            if event.get("talk_title"):
                desc_parts.append(f"Title: {event['talk_title']}")
            if event.get("abstract"):
                desc_parts.append(f"Abstract: {event['abstract']}")
            if desc_parts:
                event["description"] = "\n\n".join(desc_parts)
            else:
                main_content = soup.find("div", id="r-main") or soup.find("main")
                if main_content:
                    event["description"] = self._clean_text(main_content.get_text(separator="\n", strip=True))

        except Exception as e:
            log_error(f"Error scraping event details for {event['url']}: {e}")

    def _extract_section_content(self, header_elem):
        """Extracts all text content following a header until the next header."""
        content_parts = []
        sibling = header_elem.find_next_sibling()

        while sibling and sibling.name not in ["h1", "h2", "h3"]:
            text = sibling.get_text(" ", strip=True)
            if text:
                content_parts.append(text)
            sibling = sibling.find_next_sibling()

        return " ".join(content_parts).strip()

    def _parse_date_time(self, date_text):
        """Parses date/time string into structured metadata."""
        result = {}

        # "4 February 2026" → "2026-02-04"
        date_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_text)
        if date_match:
            day, month_name, year = date_match.groups()
            result["year"] = int(year)
            result["month"] = month_name
            month_map = {
                "january": "01", "february": "02", "march": "03", "april": "04",
                "may": "05", "june": "06", "july": "07", "august": "08",
                "september": "09", "october": "10", "november": "11", "december": "12",
            }
            month_num = month_map.get(month_name.lower(), "01")
            result["date"] = f"{year}-{month_num}-{int(day):02d}"

        # "4:00 pm" or "10:00 am - 12:00 pm"
        time_match = re.search(r"(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.IGNORECASE)
        if time_match:
            result["time_start"] = time_match.group(1).strip()

        end_time_match = re.search(r"-\s*(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.IGNORECASE)
        if end_time_match:
            result["time_end"] = end_time_match.group(1).strip()

        return result

    # ------------------------------------------------------------------
    # People scraping
    # ------------------------------------------------------------------

    def scrape_people(self):
        """Scrapes the people directory and individual profiles."""
        sources = [u for u in self.important_urls if "people" in u]
        if not sources:
            sources = self.PEOPLE_URLS

        for people_url in sources:
            log_info(f"Starting scrape of people from {people_url}")
            try:
                soup = self._fetch_page(people_url)

                profiles_to_visit = set()
                for link in soup.find_all("a", href=True):
                    href = link["href"]

                    # Drop anchor fragments — not real pages
                    if "#" in href:
                        continue

                    if "contact-page/" in href or "/faculty/" in href or "/staff/" in href:
                        if href.endswith("people/index.html") or href == people_url:
                            continue

                        if href.startswith("http"):
                            full_url = href
                        elif href.startswith("/"):
                            full_url = f"{self.BASE_URL}{href}"
                        else:
                            if people_url.endswith("index.html"):
                                base = people_url.rsplit("/", 1)[0]
                            elif people_url.endswith("/"):
                                base = people_url.rstrip("/")
                            else:
                                base = people_url
                            full_url = f"{base}/{href}"

                        profiles_to_visit.add(full_url)

                log_info(f"Found {len(profiles_to_visit)} potential people profiles to scrape.")

                for url in profiles_to_visit:
                    self._scrape_single_person_page(url)

            except Exception as e:
                log_error(f"Error scraping people index {people_url}: {e}")

        return self.people

    def _scrape_single_person_page(self, url):
        """Scrapes a single person's profile page."""
        try:
            if url in self._scraped_person_urls:
                return

            soup = self._fetch_page(url)

            name_elem = soup.find("h1", class_="header-person__name")
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Person"

            metadata = {}

            job_elem = soup.find("p", class_="header-person__job")
            if job_elem:
                metadata["position"] = job_elem.get_text(strip=True)

            dept_elem = soup.find("p", class_="header-person__department")
            if dept_elem:
                metadata["organizational_unit"] = dept_elem.get_text(strip=True)

            img_elem = soup.select_one("img.picture__image")
            if img_elem and img_elem.get("src"):
                metadata["image_url"] = img_elem["src"]

            email_elem = soup.select_one("a.header-person__contentlink.is-email")
            if email_elem:
                email = email_elem.get_text(strip=True).replace("Send an email", "")
                if not email or "@" not in email:
                    href = email_elem.get("href", "")
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "")
                if email:
                    metadata["email"] = email.strip()

            phone_elem = soup.select_one("a.header-person__contentlink.is-phone")
            if phone_elem:
                metadata["phone"] = phone_elem.get_text(strip=True)

            for area in soup.find_all("div", class_="header-person__detail_area"):
                for p in area.find_all("p"):
                    text = p.get_text(strip=True)
                    if "Room" in text and "Room finder" not in text:
                        metadata["room"] = text
                    if "Ludwigstr" in text or "Geschwister-Scholl" in text:
                        if "office_address" not in metadata:
                            metadata["office_address"] = text

            website_link = soup.find("a", string=lambda t: t and "Personal website" in t)
            if website_link:
                metadata["website"] = website_link.get("href")

            pub_header = soup.find("h2", string=lambda t: t and "Selected publications" in t)
            if pub_header:
                pub_list_container = pub_header.find_parent("div", class_="rte__content")
                if pub_list_container:
                    pub_list = pub_list_container.find(["ol", "ul"])
                    if pub_list:
                        metadata["selected_publications"] = [
                            li.get_text(" ", strip=True) for li in pub_list.find_all("li")
                        ]

            main_content = soup.find("div", id="r-main") or soup.find("main")
            description = ""

            if main_content:
                rte_divs = main_content.find_all("div", class_="rte__content")
                desc_text = []
                for div in rte_divs:
                    if div.find("h2", string=lambda t: t and "Selected publications" in t):
                        continue
                    text = div.get_text(separator=" ", strip=True)
                    if text:
                        desc_text.append(text)

                description = "\n\n".join(desc_text)

                if not description:
                    description = self._clean_text(main_content.get_text(separator=" ", strip=True))

                ri_header = main_content.find(
                    lambda tag: tag.name in ["h2", "h3"] and "Research interests" in tag.get_text()
                )
                if ri_header:
                    interests_text = ""
                    curr = ri_header.find_next_sibling()
                    while curr and curr.name not in ["h1", "h2", "h3"]:
                        interests_text += curr.get_text(separator=" ", strip=True) + " "
                        curr = curr.find_next_sibling()
                    metadata["research_interests_text"] = interests_text.strip()

            self.people.append({
                "name": name,
                "url": url,
                "description": description[:5000],
                "metadata": metadata,
                "type": "person",
                "scraped_at": datetime.now().isoformat(),
            })
            self._scraped_person_urls.add(url)

        except Exception as e:
            log_error(f"Error scraping person {url}: {e}")

    # ------------------------------------------------------------------
    # Research scraping
    # ------------------------------------------------------------------

    def scrape_research(self):
        """Scrapes the research projects and structures them."""
        log_info(f"Starting scrape of {self.RESEARCH_URL}")
        try:
            self.research = []

            categories = {
                "logic": {"name": "Logic and Philosophy of Language", "keywords": ["logic", "language", "semantic", "truth"], "items": []},
                "philsc": {"name": "Philosophy of Science", "keywords": ["science", "physics", "biology", "explanation"], "items": []},
                "decision": {"name": "Decision Theory", "keywords": ["decision", "game theory", "rationality", "choice"], "items": []},
                "structure": {"name": "Mathematical Philosophy", "keywords": ["mathematical", "formal"], "items": []},
            }

            soup = self._fetch_page(self.RESEARCH_URL)

            subpage_links = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/research/" in href and href != self.RESEARCH_URL:
                    if "/mcmp/en/research/" in href and "publications" not in href:
                        full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                        subpage_links.add(full_url)

            subpage_links.add(f"{self.BASE_URL}/mcmp/en/research/philosophy-of-machine-learning/")

            scraped_items = []
            for url in subpage_links:
                try:
                    item = self._scrape_single_research_page(url)
                    if item:
                        scraped_items.append(item)
                except Exception as e:
                    log_error(f"Failed to scrape research subpage {url}: {e}")

            for item in scraped_items:
                title_lower = item["title"].lower()
                assigned = False
                for cat_id, cat_data in categories.items():
                    if any(k in title_lower for k in cat_data["keywords"]):
                        cat_data["items"].append(item)
                        assigned = True
                        break
                if not assigned:
                    categories["structure"]["items"].append(item)

            self.research = [
                {
                    "id": cat_id,
                    "name": cat_data["name"],
                    "description": f"Research area focusing on {cat_data['name']}",
                    "subtopics": [i["title"] for i in cat_data["items"]],
                    "projects": cat_data["items"],
                    "url": self.RESEARCH_URL,
                }
                for cat_id, cat_data in categories.items()
            ]
            log_info(f"Structured research into {len(self.research)} categories.")
            return self.research

        except Exception as e:
            log_error(f"Error scraping research: {e}")
            return []

    def _scrape_single_research_page(self, url):
        """Helper to scrape a specific research page. Returns dict or None."""
        try:
            soup = self._fetch_page(url)
            title_elem = soup.find("h1")
            title = title_elem.get_text(strip=True) if title_elem else "Research Project"
            main_content = soup.find("div", id="r-main") or soup.find("main")
            if main_content:
                return {
                    "title": title,
                    "description": main_content.get_text(separator=" ", strip=True)[:5000],
                    "url": url,
                    "type": "research_project",
                    "scraped_at": datetime.now().isoformat(),
                }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # General / homepage scraping
    # ------------------------------------------------------------------

    def scrape_general(self):
        """Scrapes the home page for general info (About, History)."""
        home_url = f"{self.BASE_URL}/mcmp/en/index.html"
        log_info(f"Starting scrape of {home_url}")
        try:
            soup = self._fetch_page(home_url)
            main_content = soup.find("div", id="r-main") or soup.find("main")
            if main_content:
                for header in main_content.find_all("h2"):
                    section_title = header.get_text(strip=True)
                    if len(section_title) < 3:
                        continue

                    content = ""
                    curr = header.find_next_sibling()
                    while curr and curr.name not in ["h2", "h1"]:
                        content += curr.get_text(separator=" ", strip=True) + "\n"
                        curr = curr.find_next_sibling()

                    # Append AFTER the while loop — not inside it
                    if content.strip():
                        self.general.append({
                            "title": f"General: {section_title}",
                            "description": content.strip(),
                            "url": home_url,
                            "type": "general",
                            "scraped_at": datetime.now().isoformat(),
                        })

            return self.general
        except Exception as e:
            log_error(f"Error scraping general info: {e}")
            return []

    # ------------------------------------------------------------------
    # Reading groups scraping
    # ------------------------------------------------------------------

    def scrape_reading_groups(self):
        """Scrapes reading groups from the events page."""
        url = f"{self.BASE_URL}/mcmp/en/events/index.html"
        log_info(f"Starting scrape of reading groups from {url}")
        try:
            soup = self._fetch_page(url)
            main_content = soup.find("div", id="r-main") or soup.find("main")
            if main_content:
                header = main_content.find(
                    lambda tag: tag.name in ["h2", "h1"] and "Reading groups" in tag.get_text()
                )
                if header:
                    curr = header.find_next_sibling()
                    current_group = {}

                    while curr:
                        if curr.name in ["h1", "h2"] and "Reading groups" not in curr.get_text():
                            break

                        text = curr.get_text(separator=" ", strip=True)
                        if text:
                            link = curr.find("a")
                            is_title = link and len(text) < 100

                            if is_title:
                                if current_group:
                                    self.general.append(current_group)

                                link_url = link["href"] if link else url
                                if not link_url.startswith("http"):
                                    link_url = f"{self.BASE_URL}{link_url}"

                                if link_url == url or link_url.endswith("/events/index.html"):
                                    slug = text.lower().replace(" ", "-").replace(":", "")[:30]
                                    link_url = f"{link_url}#{slug}"

                                current_group = {
                                    "title": f"Reading Group: {text}",
                                    "description": "",
                                    "url": link_url,
                                    "type": "reading_group",
                                    "scraped_at": datetime.now().isoformat(),
                                }
                            elif current_group:
                                current_group["description"] += "\n" + text

                        curr = curr.find_next_sibling()

                    if current_group:
                        self.general.append(current_group)

            log_info("Scraped reading groups into general/events.")
            return self.general
        except Exception as e:
            log_error(f"Error scraping reading groups: {e}")
            return []

    # ------------------------------------------------------------------
    # Academic offerings scraping
    # ------------------------------------------------------------------

    def scrape_academic_offerings(self):
        """Scrapes academic program info: Bachelor, Master, PhD, and Learning Materials.

        Fetches the 'For Students' index page, splits it into 4 sections by <h2>,
        then follows the Bachelor and Master sub-pages for structured metadata.
        Does NOT follow PDF links, external links, or people profile links.
        """
        log_info(f"Starting scrape of academic offerings from {self.FOR_STUDENTS_URL}")

        _LMU_HOST = "www.philosophie.lmu.de"

        def _is_internal_content_link(href: str) -> bool:
            """True if this link should be followed as content (not PDF, profile, external, anchor)."""
            if not href or href.startswith("#"):
                return False
            if href.lower().endswith(".pdf"):
                return False
            if "/contact-page/" in href:
                return False
            # Allow relative links and links to the same host
            if href.startswith("http") and _LMU_HOST not in href:
                return False
            return True

        # --- Section keyword → offering_type mapping ---
        SECTION_MAP = {
            "bachelor": "bachelor",
            "master": "master",
            "phd": "phd",
            "ph.d": "phd",
            "doctoral": "phd",
            "learning": "learning_materials",
        }

        # --- Canonical titles for each offering type ---
        TITLE_MAP = {
            "bachelor": "Bachelor Program in Philosophy",
            "master": "Master Program in Logic and Philosophy of Science",
            "phd": "PhD Program",
            "learning_materials": "Learning Materials",
        }

        def _detect_offering_type(header_text: str) -> str:
            lower = header_text.lower()
            for kw, ot in SECTION_MAP.items():
                if kw in lower:
                    return ot
            return "general"

        try:
            soup = self._fetch_page(self.FOR_STUDENTS_URL)
            main_content = soup.find("div", id="r-main") or soup.find("main")
            if not main_content:
                log_error("Could not find main content on For Students page.")
                return self.academic_offerings

            # Split page into sections by <h2>
            for h2 in main_content.find_all("h2"):
                section_title = h2.get_text(strip=True)
                offering_type = _detect_offering_type(section_title)

                # Accumulate text and links from siblings until next <h2>/<h1>
                description_parts = []
                internal_links = []  # list of (text, full_url)
                sibling = h2.find_next_sibling()
                while sibling and sibling.name not in ["h1", "h2"]:
                    text = sibling.get_text(separator=" ", strip=True)
                    if text:
                        description_parts.append(text)
                    for a in sibling.find_all("a", href=True):
                        href = a["href"]
                        if _is_internal_content_link(href):
                            full_url = self._normalize_url(href, self.FOR_STUDENTS_URL)
                            link_text = a.get_text(strip=True)
                            internal_links.append((link_text, full_url))
                    sibling = sibling.find_next_sibling()

                description = "\n\n".join(description_parts)[:5000]
                metadata = {}

                # Extract PhD contact emails directly from the section text
                if offering_type == "phd":
                    raw_text = "\n\n".join(description_parts)
                    email_matches = re.findall(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]+', raw_text)
                    if email_matches:
                        metadata["contact_emails"] = list(dict.fromkeys(email_matches))  # dedup, preserve order

                # Learning Materials: collect non-PDF external resources
                if offering_type == "learning_materials":
                    external_resources = []
                    for a in main_content.find_all("a", href=True):
                        href = a["href"]
                        if href.lower().endswith(".pdf"):
                            continue
                        if href.startswith("#"):
                            continue
                        link_text = a.get_text(strip=True)
                        # Only collect links from the learning_materials section area
                        # (we're already inside the sibling loop above, but collect here from raw soup)
                    # Re-scan siblings for non-PDF links specifically
                    sibling2 = h2.find_next_sibling()
                    while sibling2 and sibling2.name not in ["h1", "h2"]:
                        for a in sibling2.find_all("a", href=True):
                            href = a["href"]
                            if href.lower().endswith(".pdf") or href.startswith("#"):
                                continue
                            link_text = a.get_text(strip=True)
                            full_url = self._normalize_url(href, self.FOR_STUDENTS_URL)
                            external_resources.append({"text": link_text, "url": full_url})
                        sibling2 = sibling2.find_next_sibling()
                    if external_resources:
                        metadata["external_resources"] = external_resources

                # Follow sub-pages for Bachelor and Master
                if offering_type == "bachelor":
                    metadata.update(self._scrape_bachelor_details())
                elif offering_type == "master":
                    metadata.update(self._scrape_master_details())

                # Determine canonical URL for this entry
                if offering_type == "bachelor":
                    entry_url = self.BACHELOR_URL
                elif offering_type == "master":
                    entry_url = self.MASTER_URL
                else:
                    entry_url = self.FOR_STUDENTS_URL

                self.academic_offerings.append({
                    "title": TITLE_MAP.get(offering_type, section_title),
                    "offering_type": offering_type,
                    "url": entry_url,
                    "description": description,
                    "type": "academic_offering",
                    "metadata": metadata,
                    "scraped_at": datetime.now().isoformat(),
                })
                log_info(f"Scraped academic offering section: '{section_title}' (type={offering_type})")

        except Exception as e:
            log_error(f"Error scraping academic offerings: {e}")

        log_info(f"Scraped {len(self.academic_offerings)} academic offering sections.")
        return self.academic_offerings

    def _scrape_bachelor_details(self) -> dict:
        """Fetches the Bachelor program page and returns structured metadata."""
        try:
            soup = self._fetch_page(self.BACHELOR_URL)
            main = soup.find("div", id="r-main") or soup.find("main")
            if not main:
                return {}
            full_text = main.get_text(separator=" ", strip=True)
            metadata = {
                "ects": 180,
                "duration": "6 semesters",
                "language": "German (with select seminars in English)",
                "application_deadline": "July 15",
                "start": "Winter semester only",
                "note": "Mandatory minor subject (60 ECTS). Full-time, in-person study required.",
            }
            # Extract admission requirement sentence if present
            if "Hochschulreife" in full_text or "university entrance" in full_text.lower():
                metadata["admission_requirements"] = [
                    "General university entrance qualification (Abitur/Hochschulreife)",
                    "International applicants apply through the International Office",
                ]
            return metadata
        except Exception as e:
            log_error(f"Error scraping Bachelor details: {e}")
            return {}

    def _scrape_master_details(self) -> dict:
        """Fetches the Master program page and returns structured metadata."""
        try:
            soup = self._fetch_page(self.MASTER_URL)
            main = soup.find("div", id="r-main") or soup.find("main")
            if not main:
                return {}
            full_text = main.get_text(separator=" ", strip=True)

            metadata = {
                "ects": 120,
                "duration": "2 years / 4 semesters",
                "language": "English",
                "cost": "Free (approx. €150/semester fee for student services and transport)",
                "founded": 2012,
            }

            # Application deadline
            deadline_match = re.search(r"(?:deadline|by)[^\d]*(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|June\s+\d{1,2},?\s+\d{4})", full_text, re.IGNORECASE)
            if deadline_match:
                metadata["application_deadline"] = deadline_match.group(1).strip()
            else:
                metadata["application_deadline"] = "June 10"  # known from page

            # Application opens
            opens_match = re.search(r"(?:application[s]?\s+open[s]?|from)[^\d]*(\w+\s+\d{1,2},?\s+\d{4}|November\s+\d{1,2},?\s+\d{4})", full_text, re.IGNORECASE)
            if opens_match:
                metadata["application_opens"] = opens_match.group(1).strip()
            else:
                metadata["application_opens"] = "November 1"  # known from page

            # Contact email
            email_matches = re.findall(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]+', full_text)
            if email_matches:
                metadata["contact_email"] = email_matches[0]

            # Coordinators
            coordinators = []
            for name in ["Norbert Gratzl", "Alexander Reutlinger"]:
                if name in full_text:
                    coordinators.append(name)
            if coordinators:
                metadata["coordinators"] = coordinators

            # Required documents — look for a list near "application" heading
            req_docs = []
            app_header = main.find(
                lambda tag: tag.name in ["h2", "h3"] and "application" in tag.get_text(strip=True).lower()
            )
            if app_header:
                curr = app_header.find_next_sibling()
                while curr and curr.name not in ["h1", "h2", "h3"]:
                    if curr.name in ["ul", "ol"]:
                        req_docs = [li.get_text(" ", strip=True) for li in curr.find_all("li")]
                        break
                    curr = curr.find_next_sibling()
            if req_docs:
                metadata["required_documents"] = req_docs
            else:
                # Fallback: known documents
                metadata["required_documents"] = [
                    "Cover letter (1–2 pages)",
                    "CV",
                    "Official transcript",
                    "Writing sample (max 15 pages)",
                    "English proficiency certificate (C1)",
                    "Two letters of recommendation",
                ]

            # Admission requirements
            metadata["admission_requirements"] = [
                "Previous degree equivalent to at least 150 ECTS",
                "Average grade of 2.0 or better",
                "English proficiency: C1 level",
                "German language: A1 level by end of Year 1",
            ]

            # Open to (eligible disciplines)
            disciplines_header = main.find(
                lambda tag: tag.name in ["h2", "h3"] and any(
                    kw in tag.get_text(strip=True).lower()
                    for kw in ["open to", "eligible", "background", "who can apply"]
                )
            )
            if disciplines_header:
                curr = disciplines_header.find_next_sibling()
                while curr and curr.name not in ["h1", "h2", "h3"]:
                    if curr.name in ["ul", "ol"]:
                        metadata["open_to"] = [li.get_text(" ", strip=True) for li in curr.find_all("li")]
                        break
                    curr = curr.find_next_sibling()

            return metadata
        except Exception as e:
            log_error(f"Error scraping Master details: {e}")
            return {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _log_changes(self):
        """Calculates differences between old and new data and logs them."""
        log_file = "data/scraping_logs.json"

        datasets = {
            "events": (self.events, "data/raw_events.json", "url"),
            "people": (self.people, "data/people.json", "url"),
            "research": (self.research, "data/research.json", "id"),
            "general": (self.general, "data/general.json", lambda x: f"{x.get('url', '')}_{x.get('title', '')}"),
            "academic_offerings": (self.academic_offerings, "data/academic_offerings.json", lambda x: f"{x.get('url', '')}_{x.get('offering_type', '')}"),
        }

        changes_summary = {}
        total_changes = 0

        for name, (new_data, file_path, uuid_key) in datasets.items():
            old_data = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                except Exception as e:
                    log_error(f"Error reading old {name} data: {e}")

            def get_id(item, key=uuid_key):
                return key(item) if callable(key) else item.get(key)

            old_map = {get_id(item): item for item in old_data if get_id(item)}
            new_map = {get_id(item): item for item in new_data if get_id(item)}

            added, removed, updated = [], [], []

            for nid, nitem in new_map.items():
                if nid not in old_map:
                    added.append(nitem.get("title") or nitem.get("name") or nitem.get("id") or nid)
                else:
                    oitem_copy = {k: v for k, v in old_map[nid].items() if k != "scraped_at"}
                    nitem_copy = {k: v for k, v in nitem.items() if k != "scraped_at"}
                    if oitem_copy != nitem_copy:
                        updated.append(nitem.get("title") or nitem.get("name") or nitem.get("id") or nid)

            for oid, oitem in old_map.items():
                if oid not in new_map:
                    removed.append(oitem.get("title") or oitem.get("name") or oitem.get("id") or oid)

            if added or removed or updated:
                changes_summary[name] = {"added": added, "removed": removed, "updated": updated}
                total_changes += len(added) + len(removed) + len(updated)

        if total_changes > 0 or not os.path.exists(log_file):
            log_entries = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        log_entries = json.load(f)
                except Exception:
                    pass

            log_entries.append({
                "timestamp": datetime.now().isoformat(),
                "changes": changes_summary,
            })

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=4, ensure_ascii=False)

            log_info(f"Logged {total_changes} changes to {log_file}")
            self._print_update_summary(changes_summary)
        else:
            log_info("No changes detected in datasets.")
            print("\n--- Update Summary ---")
            print("No changes detected.")
            print("----------------------\n")

    def _print_update_summary(self, changes_summary):
        print("\n--- Update Summary ---")
        for category, diff in changes_summary.items():
            added = len(diff.get("added", []))
            removed = len(diff.get("removed", []))
            updated = len(diff.get("updated", []))
            print(f"  {category}: +{added} added, -{removed} removed, ~{updated} updated")
        print("----------------------\n")

    def _accumulate(self, new_data, file_path, key):
        """Merge new_data into existing file: update matching entries, add new ones, never remove."""
        existing = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception as e:
                log_error(f"Error reading {file_path} for accumulation: {e}")

        def get_id(item):
            return key(item) if callable(key) else item.get(key)

        merged = {get_id(item): item for item in existing if get_id(item)}
        for item in new_data:
            item_id = get_id(item)
            if item_id:
                merged[item_id] = item
        return list(merged.values())

    def save_to_json(self):
        """Saves scraped data to JSON files, accumulating with existing data.

        Entries are NEVER removed. Newly scraped data updates existing entries
        (by URL/id) and adds new ones. Entries absent from the current scrape
        are preserved as-is.
        """
        os.makedirs("data", exist_ok=True)

        self.events = self._accumulate(self.events, "data/raw_events.json", "url")
        self.people = self._accumulate(self.people, "data/people.json", "url")
        self.research = self._accumulate(self.research, "data/research.json", "id")
        self.general = self._accumulate(
            self.general, "data/general.json",
            lambda x: f"{x.get('url', '')}_{x.get('title', '')}",
        )
        self.academic_offerings = self._accumulate(
            self.academic_offerings, "data/academic_offerings.json",
            lambda x: f"{x.get('url', '')}_{x.get('offering_type', '')}",
        )

        self._log_changes()

        with open("data/raw_events.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=4, ensure_ascii=False)

        with open("data/people.json", "w", encoding="utf-8") as f:
            json.dump(self.people, f, indent=4, ensure_ascii=False)

        with open("data/research.json", "w", encoding="utf-8") as f:
            json.dump(self.research, f, indent=4, ensure_ascii=False)

        with open("data/general.json", "w", encoding="utf-8") as f:
            json.dump(self.general, f, indent=4, ensure_ascii=False)

        with open("data/academic_offerings.json", "w", encoding="utf-8") as f:
            json.dump(self.academic_offerings, f, indent=4, ensure_ascii=False)

        log_info(
            f"Saved {len(self.events)} events, {len(self.people)} people, "
            f"{len(self.research)} research items, {len(self.general)} general items, "
            f"{len(self.academic_offerings)} academic offering sections."
        )

        try:
            log_info("Updating institutional graph...")
            build_graph.run()
            log_info("Graph updated successfully.")
        except Exception as e:
            log_error(f"Failed to update graph: {e}")


if __name__ == "__main__":
    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.scrape_people()
    scraper.scrape_research()
    scraper.scrape_general()
    scraper.scrape_reading_groups()
    scraper.save_to_json()
