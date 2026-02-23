import requests
from bs4 import BeautifulSoup
import json
import os
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
    # Fallback/warnings if needed, but assuming structure holds
    import src.utils.build_graph as build_graph

class MCMPScraper:
    BASE_URL = "https://www.philosophie.lmu.de"
    EVENT_SOURCES = [
        f"{BASE_URL}/mcmp/en/latest-news/events-overview/index.html",
        f"{BASE_URL}/mcmp/en/events/index.html",
        f"{BASE_URL}/mcmp/en/index.html"
    ]
    # Fallback if file not found, but we prefer reading from file
    PEOPLE_URLS = [f"{BASE_URL}/mcmp/en/people/index.html"]
    RESEARCH_URL = f"{BASE_URL}/mcmp/en/research/index.html"
    EVENTS_JSON_URL = f"{BASE_URL}/mcmp/site_tech/json-newsboard/json-events-newsboard-en.json"
    NEWS_JSON_URL = f"{BASE_URL}/mcmp/site_tech/json-newsboard/json-news-newsboard-en.json"

    def __init__(self):
        self.events = []
        self.people = []
        self.research = []
        self.general = []
        self.news = []
        self.important_urls = self.load_important_urls()

    def _get(self, url):
        """Wrapper around requests.get that forces UTF-8 encoding."""
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response

    def _clean_text(self, text):
        """Removes common noise from scraped text."""
        if not text:
            return ""
            
        lines = text.split('\n')
        cleaned_lines = []
        skip_mode = False
        
        # Heuristics to skip navigation and footer
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip breadcrumbs start
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

    def scrape_events(self):
        """Scrapes events using the JSON API as primary source, with static/Selenium fallback.

        Primary: JSON API (json-events-newsboard-en.json) — returns all events reliably.
        Fallback: Selenium or static scraping for any additional events not in the API.
        """
        seen_urls = set()  # URL-based deduplication

        # Primary source: JSON API (bypasses dynamic JS loading entirely)
        log_info(f"Fetching events index from {self.EVENTS_JSON_URL}")
        try:
            response = self._get(self.EVENTS_JSON_URL)
            api_events = json.loads(response.text)
            log_info(f"JSON API returned {len(api_events)} events")

            for item in api_events:
                link = item.get("link", {})
                url = link.get("href", "")
                title = link.get("text", "")

                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Pre-populate metadata from API (date, dateEnd)
                api_date = item.get("date", "")[:10]  # "2026-02-04T..." -> "2026-02-04"
                api_date_end = item.get("dateEnd", "")[:10]
                metadata = {}
                if api_date:
                    metadata["date"] = api_date
                if api_date_end and api_date_end != api_date:
                    metadata["date_end"] = api_date_end

                self.events.append({
                    "title": title,
                    "url": url,
                    "metadata": metadata,
                    "scraped_at": datetime.now().isoformat()
                })
        except Exception as e:
            log_error(f"JSON API failed, falling back to HTML scraping: {e}")

        # Fallback: Selenium for dynamic pages (if API failed or missed events)
        if SELENIUM_AVAILABLE:
            events_overview_url = f"{self.BASE_URL}/mcmp/en/latest-news/events-overview/index.html"
            log_info(f"Supplementing with Selenium scrape of {events_overview_url}")
            try:
                event_links = self._fetch_events_with_selenium(events_overview_url)
                added = 0
                for url, title in event_links:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        self.events.append({
                            "title": title,
                            "url": url,
                            "scraped_at": datetime.now().isoformat()
                        })
                        added += 1
                if added:
                    log_info(f"Selenium added {added} extra events not in API")
            except Exception as e:
                log_error(f"Selenium supplemental scrape failed: {e}")

        # Fallback: Static scraping for other source pages
        for source_url in self.EVENT_SOURCES:
            if "events-overview" in source_url:
                continue  # Already covered by API + Selenium
            try:
                response = self._get(source_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                event_links = soup.select('a.filterable-list__list-item-link.is-events')
                if not event_links:
                    event_links = [
                        link for link in soup.find_all('a', href=True)
                        if self._is_event_link(link['href'])
                    ]
                added = 0
                for link in event_links:
                    href = link.get('href', '')
                    full_url = self._normalize_url(href, source_url)
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    text = link.get_text(strip=True)
                    title = text or href.split('/')[-1].replace('.html', '').replace('-', ' ').title()
                    self.events.append({
                        "title": title,
                        "url": full_url,
                        "scraped_at": datetime.now().isoformat()
                    })
                    added += 1
                if added:
                    log_info(f"Static scrape of {source_url} added {added} extra events")
            except Exception as e:
                log_error(f"Error scraping {source_url}: {e}")

        log_info(f"Found {len(self.events)} unique event links in total.")
        
        # Now scrape details for all found events
        for i, event in enumerate(self.events):
            log_info(f"Scraping event {i+1}/{len(self.events)}: {event['title']}")
            self.scrape_event_details(event)
            
        return self.events
    
    def _fetch_events_with_selenium(self, url):
        """Uses Selenium to load all events from a page with 'Load more' button.
        
        Returns list of (url, title) tuples.
        """
        # Setup headless Chrome
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
                options=chrome_options
            )
            driver.get(url)
            
            # Wait for initial content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.filterable-list__list-item-link.is-events"))
            )
            
            # Click "Load more" button repeatedly until it disappears
            max_clicks = 10  # Safety limit
            clicks = 0
            while clicks < max_clicks:
                try:
                    load_more_btn = driver.find_element(By.CSS_SELECTOR, "button.filterable-list__load-more")
                    if load_more_btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView();", load_more_btn)
                        driver.execute_script("arguments[0].click();", load_more_btn)
                        time.sleep(1)  # Wait for new content
                        clicks += 1
                        log_info(f"Clicked 'Load more' button ({clicks} times)")
                    else:
                        break
                except (NoSuchElementException, TimeoutException):
                    break  # No more "Load more" button
            
            # Extract all event links
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
    
    def _normalize_url(self, href, source_url):
        """Normalizes a URL to absolute form."""
        if href.startswith("http"):
            return href
        elif href.startswith("/"):
            return f"{self.BASE_URL}{href}"
        else:
            base_path = source_url.rsplit('/', 1)[0]
            return f"{base_path}/{href}".replace("/./", "/")

    def scrape_event_details(self, event):
        """Scrapes details for a single event with structured field extraction."""
        try:
            response = self._get(event['url'])
            soup = BeautifulSoup(response.text, 'html.parser')

            # Preserve any metadata pre-populated from the JSON API (date, date_end)
            metadata = event.get("metadata", {}).copy()

            # Extract speaker from main H1 (e.g., "Talk: Simon Saunders (Oxford)")
            h1 = soup.find('h1')
            if h1:
                speaker_text = h1.get_text(strip=True)
                # Parse speaker from title like "Talk: Name (Affiliation)"
                if ':' in speaker_text:
                    speaker_part = speaker_text.split(':', 1)[1].strip()
                    metadata['speaker'] = speaker_part
            
            # Extract labeled sections (Title, Abstract, Date, Location)
            for h2 in soup.find_all('h2'):
                label = h2.get_text(strip=True).rstrip(':').lower()
                
                if label == 'title':
                    event['talk_title'] = self._extract_section_content(h2)
                elif label == 'abstract':
                    event['abstract'] = self._extract_section_content(h2)
                elif label == 'date':
                    date_text = self._extract_section_content(h2)
                    parsed = self._parse_date_time(date_text)
                    # Only fill in fields not already set by the JSON API
                    for k, v in parsed.items():
                        if k not in metadata:
                            metadata[k] = v
            
            # Extract location from address tag (most reliable)
            address = soup.find('address')
            if address:
                location = address.get_text(' ', strip=True)
                # Clean up location string
                location = ' '.join(location.split())  # Normalize whitespace
                metadata['location'] = location
            
            # Fallback: Try dl/dt/dd structure for any missing metadata
            for dl in soup.find_all('dl'):
                for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                    key = dt.get_text(strip=True).lower().replace(':', '')
                    val = dd.get_text(' ', strip=True)
                    if key and val and key not in metadata:
                        metadata[key] = val
            
            event['metadata'] = metadata
            
            # Build a clean description from abstract + title
            desc_parts = []
            if event.get('talk_title'):
                desc_parts.append(f"Title: {event['talk_title']}")
            if event.get('abstract'):
                desc_parts.append(f"Abstract: {event['abstract']}")
            if desc_parts:
                event['description'] = '\n\n'.join(desc_parts)
            else:
                # Fallback to raw content
                main_content = soup.find('div', id='r-main') or soup.find('main')
                if main_content:
                    event['description'] = self._clean_text(main_content.get_text(separator='\n', strip=True))
            
        except Exception as e:
            log_error(f"Error scraping event details for {event['url']}: {e}")
    
    def _extract_section_content(self, header_elem):
        """Extracts all text content following a header until the next header."""
        content_parts = []
        sibling = header_elem.find_next_sibling()
        
        while sibling and sibling.name not in ['h1', 'h2', 'h3']:
            text = sibling.get_text(' ', strip=True)
            if text:
                content_parts.append(text)
            sibling = sibling.find_next_sibling()
        
        return ' '.join(content_parts).strip()
    
    def _parse_date_time(self, date_text):
        """Parses date/time string into structured metadata."""
        import re
        
        result = {}
        
        # Try to extract ISO date (e.g., "4 February 2026")
        date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
        if date_match:
            day, month_name, year = date_match.groups()
            result['year'] = int(year)
            result['month'] = month_name
            
            # Convert to ISO date
            month_map = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12'
            }
            month_num = month_map.get(month_name.lower(), '01')
            result['date'] = f"{year}-{month_num}-{int(day):02d}"
        
        # Try to extract time (e.g., "4:00 pm" or "10:00 am - 12:00 pm")
        time_match = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', date_text, re.IGNORECASE)
        if time_match:
            result['time_start'] = time_match.group(1).strip()
        
        end_time_match = re.search(r'-\s*(\d{1,2}:\d{2}\s*[ap]m)', date_text, re.IGNORECASE)
        if end_time_match:
            result['time_end'] = end_time_match.group(1).strip()
        
        return result

    def scrape_people(self):
        """Scrapes the people directory and individual profiles."""
        # Use important URLs if available, otherwise default
        sources = [u for u in self.important_urls if "people" in u]
        if not sources:
            sources = self.PEOPLE_URLS

        for people_url in sources:
            log_info(f"Starting scrape of people from {people_url}")
            try:
                response = self._get(people_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                person_links = soup.find_all('a', href=True)
                profiles_to_visit = set()

                for link in person_links:
                    href = link['href']
                    # Heuristic for people profiles
                    # The links observed are relative like "contact-page/..."
                    if "contact-page/" in href or "/faculty/" in href or "/staff/" in href:
                         # Exclude the index page itself
                         if href.endswith("people/index.html") or href == people_url:
                             continue

                         if href.startswith("http"):
                             full_url = href
                         elif href.startswith("/"):
                             full_url = f"{self.BASE_URL}{href}"
                         else:
                             # Relative to the people_url (which should end in / or /index.html)
                             if people_url.endswith("index.html"):
                                 base = people_url.rsplit('/', 1)[0]
                             elif people_url.endswith("/"):
                                 base = people_url.rstrip('/')
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
            if url in [p['url'] for p in self.people]:
                return

            response = self._get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Name
            name_elem = soup.find('h1', class_='header-person__name')
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Person"
            
            # New Fields Extraction
            metadata = {}
            
            # 1. Position/Role
            job_elem = soup.find('p', class_='header-person__job')
            if job_elem:
                metadata['position'] = job_elem.get_text(strip=True)
                
            # 2. Organizational Unit
            dept_elem = soup.find('p', class_='header-person__department')
            if dept_elem:
                metadata['organizational_unit'] = dept_elem.get_text(strip=True)
                
            # 3. Image URL
            img_elem = soup.select_one('img.picture__image')
            if img_elem and img_elem.get('src'):
                metadata['image_url'] = img_elem['src']

            # 4. Email
            email_elem = soup.select_one('a.header-person__contentlink.is-email')
            if email_elem:
                email = email_elem.get_text(strip=True).replace("Send an email", "")
                # If text was just "Send an email", try mailto
                if not email or "@" not in email:
                    href = email_elem.get('href', '')
                    if href.startswith('mailto:'):
                        email = href.replace('mailto:', '')
                if email:
                    metadata['email'] = email.strip()

            # 5. Phone
            phone_elem = soup.select_one('a.header-person__contentlink.is-phone')
            if phone_elem:
                metadata['phone'] = phone_elem.get_text(strip=True)

            # 6. Room / Office Address
            # Look for div.header-person__detail_area and check p tags
            detail_areas = soup.find_all('div', class_='header-person__detail_area')
            for area in detail_areas:
                p_tags = area.find_all('p')
                for p in p_tags:
                    text = p.get_text(strip=True)
                    if "Room" in text and "Room finder" not in text:
                        metadata['room'] = text
                    # Fallback for office if not found yet
                    if "Ludwigstr" in text or "Geschwister-Scholl" in text:
                         if 'office_address' not in metadata:
                             metadata['office_address'] = text

            # 7. Website
            # Look for link with text "Personal website"
            website_link = soup.find('a', string=lambda t: t and "Personal website" in t)
            if website_link:
                metadata['website'] = website_link.get('href')

            # 8. Selected Publications
            # Find h2 with text "Selected publications" and get next sibling list
            pub_header = soup.find('h2', string=lambda t: t and "Selected publications" in t)
            if pub_header:
                # The list is usually in the next sibling or container
                # Structure: h2 -> p -> ol/ul  OR h2 -> div -> ol/ul
                # We can try to find the next ol or ul
                pub_list_container = pub_header.find_parent('div', class_='rte__content')
                if pub_list_container:
                    pub_list = pub_list_container.find(['ol', 'ul'])
                    if pub_list:
                        publications = []
                        for li in pub_list.find_all('li'):
                            publications.append(li.get_text(" ", strip=True))
                        metadata['selected_publications'] = publications

            # Main content for description (fallback/additional)
            main_content = soup.find('div', id='r-main') or soup.find('main')
            description = ""
            
            if main_content:
                # Clean description: remove the header person part which we already scraped
                # We can just extract text from rte__content divs which usually hold the main text
                rte_divs = main_content.find_all('div', class_='rte__content')
                desc_text = []
                for div in rte_divs:
                    # Skip if it's the publications section we already handled
                    if div.find('h2', string=lambda t: t and "Selected publications" in t):
                        continue
                    
                    # Extract text
                    text = div.get_text(separator=' ', strip=True)
                    if text:
                        desc_text.append(text)
                
                description = "\n\n".join(desc_text)
                
                # Fallback if no rte content found (some pages might differ)
                if not description:
                     description = self._clean_text(main_content.get_text(separator=' ', strip=True))

                # Extract Research Interests specifically if not already caught (usually in rte)
                # But we can look for specific header in the description text or structure
                ri_header = main_content.find(lambda tag: tag.name in ['h2', 'h3'] and "Research interests" in tag.get_text())
                if ri_header:
                    interests_text = ""
                    curr = ri_header.find_next_sibling()
                    while curr and curr.name not in ['h1', 'h2', 'h3']:
                        interests_text += curr.get_text(separator=' ', strip=True) + " "
                        curr = curr.find_next_sibling()
                    metadata['research_interests_text'] = interests_text.strip()

            self.people.append({
                "name": name,
                "url": url,
                "description": description[:5000],
                "metadata": metadata,
                "type": "person",
                "scraped_at": datetime.now().isoformat()
            })
        except Exception as e:
            log_error(f"Error scraping person {url}: {e}")

    def scrape_research(self):
        """Scrapes the research projects and structures them."""
        log_info(f"Starting scrape of {self.RESEARCH_URL}")
        try:
            self.research = [] # Reset
            
            # Defined High-Level Categories (Chairs/Areas)
            # We will try to bin scraped pages into these
            categories = {
                "logic": {"name": "Logic and Philosophy of Language", "keywords": ["logic", "language", "semantic", "truth"], "items": []},
                "philsc": {"name": "Philosophy of Science", "keywords": ["science", "physics", "biology", "explanation"], "items": []},
                "decision": {"name": "Decision Theory", "keywords": ["decision", "game theory", "rationality", "choice"], "items": []},
                "structure": {"name": "Mathematical Philosophy", "keywords": ["mathematical", "formal"], "items": []} # Fallback
            }

            response = self._get(self.RESEARCH_URL)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            subpage_links = set()
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/research/" in href and href != self.RESEARCH_URL:
                     if "/mcmp/en/research/" in href and "publications" not in href:
                         full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                         subpage_links.add(full_url)
            
            # Ensure the specific ML page requested is included
            ml_page = f"{self.BASE_URL}/mcmp/en/research/philosophy-of-machine-learning/"
            subpage_links.add(ml_page)

            scraped_items = []
            for url in subpage_links:
                try:
                    item = self._scrape_single_research_page(url)
                    if item:
                        scraped_items.append(item)
                except Exception as e:
                    log_error(f"Failed to scrape research subpage {url}: {e}")

            # Categorize items
            for item in scraped_items:
                title_lower = item['title'].lower()
                desc_lower = item['description'].lower()
                
                assigned = False
                for cat_id, cat_data in categories.items():
                    if any(k in title_lower for k in cat_data['keywords']):
                        cat_data['items'].append(item)
                        assigned = True
                        break
                
                if not assigned:
                    # Fallback to general or mapped to content keywords
                    categories['structure']['items'].append(item)

            # Transform to new hierarchical structure for research.json
            final_structure = []
            for cat_id, cat_data in categories.items():
                # Always include the core categories so TopicMatcher can use them
                # Extract subtopics names from items
                subtopics = [i['title'] for i in cat_data['items']]
                
                final_structure.append({
                    "id": cat_id,
                    "name": cat_data['name'],
                    "description": f"Research area focusing on {cat_data['name']}",
                    "subtopics": subtopics,
                    "projects": cat_data['items'], # Keep full details nested
                    "url": self.RESEARCH_URL
                })
            
            self.research = final_structure
            log_info(f"Structured research into {len(self.research)} categories.")
            return self.research
            
        except Exception as e:
            log_error(f"Error scraping research: {e}")
            return []

    def _scrape_single_research_page(self, url):
        """Helper to scrape a specific research page. Returns dict or None."""
        try:
            response = self._get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else "Research Project"
            
            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
                return {
                    "title": title,
                    "description": text[:5000],
                    "url": url,
                    "type": "research_project",
                    "scraped_at": datetime.now().isoformat()
                }
        except Exception as e:
            return None

    def scrape_general(self):
        """Scrapes the home page for general info (About, History)."""
        home_url = f"{self.BASE_URL}/mcmp/en/index.html"
        log_info(f"Starting scrape of {home_url}")
        try:
            response = self._get(home_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                # Extract sections like "About the MCMP", "Our history", etc.
                # CAPTURE ALL SECTIONS regardless of typo in title
                headers = main_content.find_all(['h2'])
                for header in headers:
                    section_title = header.get_text(strip=True)
                    # Skip empty titles or navigation elements if necessary
                    if len(section_title) < 3: 
                        continue

                    content = ""
                    curr = header.find_next_sibling()
                    while curr and curr.name not in ['h2', 'h1']:
                        content += curr.get_text(separator=' ', strip=True) + "\n"
                        curr = curr.find_next_sibling()
                        
                        if content.strip():
                            self.general.append({
                                "title": f"General: {section_title}",
                                "description": content.strip(),
                                "url": home_url,
                                "type": "general",
                                "scraped_at": datetime.now().isoformat()
                            })
            
            return self.general
        except Exception as e:
             log_error(f"Error scraping general info: {e}")
             return []

    def scrape_reading_groups(self):
        """Scrapes reading groups from the events page."""
        url = f"{self.BASE_URL}/mcmp/en/events/index.html"
        log_info(f"Starting scrape of reading groups from {url}")
        try:
            response = self._get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Reading groups seem to be in an accordion or headers under "Reading groups" section
            # We look for the "Reading groups" header and then parse subsequent content
            
            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                # Find the "Reading groups" header
                header = main_content.find(lambda tag: tag.name in ['h2', 'h1'] and "Reading groups" in tag.get_text())
                
                if header:
                    # Iterate through siblings to find groups
                    # Structure might be: Header -> p/div (content) -> Header -> ...
                    curr = header.find_next_sibling()
                    current_group = {}
                    
                    while curr:
                        # Stop if we hit a new major section (e.g. "Event policy")
                        if curr.name in ['h1', 'h2'] and "Reading groups" not in curr.get_text():
                            break
                        
                        # In the observed chunk, group titles were links or text followed by description
                        # e.g. [Philosophy of machine learning]... We meet...
                        
                        text = curr.get_text(separator=' ', strip=True)
                        if text:
                            # Heuristic: If it looks like a title (short, maybe has link)
                            is_title = False
                            link = curr.find('a')
                            if link and len(text) < 100:
                                is_title = True
                            
                            if is_title:
                                # Save previous if exists
                                if current_group:
                                    self.general.append(current_group)
                                
                                title = text
                                link_url = link['href'] if link else url
                                if not link_url.startswith("http"):
                                    link_url = f"{self.BASE_URL}{link_url}"
                                
                                # Ensure uniqueness if multiple groups share the same base URL (e.g. no specific anchor)
                                if link_url == url or link_url.endswith("/events/index.html"):
                                     slug = title.lower().replace(" ", "-").replace(":", "")[:30]
                                     link_url = f"{link_url}#{slug}"

                                current_group = {
                                    "title": f"Reading Group: {title}",
                                    "description": "",
                                    "url": link_url,
                                    "type": "reading_group",
                                    "scraped_at": datetime.now().isoformat()
                                }
                            elif current_group:
                                current_group["description"] += "\n" + text
                        
                        curr = curr.find_next_sibling()
                    
                    # Append the last one
                    if current_group:
                         self.general.append(current_group)

            log_info(f"Scraped reading groups into general/events.")
            return self.general
        except Exception as e:
            log_error(f"Error scraping reading groups: {e}")
            return []

    def scrape_news(self):
        """Scrapes MCMP news from the JSON newsboard API and individual news pages."""
        log_info(f"Fetching news index from {self.NEWS_JSON_URL}")
        try:
            response = self._get(self.NEWS_JSON_URL)
            news_items = json.loads(response.text)
            log_info(f"Found {len(news_items)} news items in API")

            for item in news_items:
                link = item.get("link", {})
                url = link.get("href", "")
                title = link.get("text", "")

                if not url:
                    continue

                news_entry = {
                    "title": title,
                    "url": url,
                    "metadata": {
                        "date": item.get("date", "")[:10],  # "2026-02-02T14:..." -> "2026-02-02"
                        "category": item.get("categoryHeadline", "News"),
                    },
                    "description": item.get("description", ""),
                    "type": "news",
                    "scraped_at": datetime.now().isoformat()
                }

                # Scrape individual news page for full content
                self._scrape_news_details(news_entry)
                self.news.append(news_entry)

            log_info(f"Scraped {len(self.news)} news items with details.")
            return self.news
        except Exception as e:
            log_error(f"Error scraping news: {e}")
            return []

    def _scrape_news_details(self, news_entry):
        """Scrapes the full content of an individual news page."""
        try:
            response = self._get(news_entry['url'])
            soup = BeautifulSoup(response.text, 'html.parser')

            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                # Extract full body text from rte__content divs
                rte_divs = main_content.find_all('div', class_='rte__content')
                if rte_divs:
                    text_parts = [div.get_text(separator=' ', strip=True) for div in rte_divs]
                    news_entry['description'] = '\n\n'.join(p for p in text_parts if p)
                else:
                    news_entry['description'] = self._clean_text(
                        main_content.get_text(separator='\n', strip=True)
                    )
        except Exception as e:
            log_error(f"Error scraping news details for {news_entry['url']}: {e}")

    def _merge_and_save(self, existing_file, new_data, key_field="url"):
        """Merges new data with existing JSON data, preserving old records."""
        merged_data = {}
        
        # 1. Load existing data
        if os.path.exists(existing_file):
            try:
                with open(existing_file, 'r', encoding='utf-8') as f:
                    old_list = json.load(f)
                    for item in old_list:
                        # Use URL as key if available, otherwise title or fallback
                        key = item.get(key_field)
                        if key:
                            merged_data[key] = item
            except (json.JSONDecodeError, OSError) as e:
                log_error(f"Could not read existing file {existing_file}: {e}")

        # 2. Update/Add new data
        for item in new_data:
            key = item.get(key_field)
            if key:
                # Update existing or add new
                merged_data[key] = item
            else:
                # If no key, just append? Or skip?
                # Probably append to a list, but for now let's assume valid objects have keys
                pass

        return list(merged_data.values())

    def save_to_json(self):
        """Saves scraped data to JSON files, merging with existing data."""
        os.makedirs("data", exist_ok=True)
        
        # Merge and Save Events
        full_events = self._merge_and_save("data/raw_events.json", self.events, "url")
        with open("data/raw_events.json", 'w', encoding='utf-8') as f:
            json.dump(full_events, f, indent=4, ensure_ascii=False)
        
        # Merge and Save People
        full_people = self._merge_and_save("data/people.json", self.people, "url")
        with open("data/people.json", 'w', encoding='utf-8') as f:
            json.dump(full_people, f, indent=4, ensure_ascii=False)
            
        # Merge and Save Research
        if os.path.exists("data/research.json"):
            try:
                with open("data/research.json", 'r', encoding='utf-8') as f:
                    old_research = json.load(f)
                
                old_cats = {c.get("id"): c for c in old_research}
                new_cats = {c.get("id"): c for c in self.research}
                
                for cat_id, new_cat in new_cats.items():
                    if cat_id in old_cats:
                        old_cat = old_cats[cat_id]
                        
                        # Merge projects preserving old ones
                        old_projects = {p.get("url", p.get("title")): p for p in old_cat.get("projects", [])}
                        for p in new_cat.get("projects", []):
                            key = p.get("url", p.get("title"))
                            old_projects[key] = p
                        new_cat["projects"] = list(old_projects.values())
                        
                        # Merge subtopics
                        old_subtopics = set(old_cat.get("subtopics", []))
                        old_subtopics.update(new_cat.get("subtopics", []))
                        new_cat["subtopics"] = list(old_subtopics)
                        
                # Keep old categories not in new scrape
                for cat_id, old_cat in old_cats.items():
                    if cat_id not in new_cats:
                        new_cats[cat_id] = old_cat
                        
                self.research = list(new_cats.values())
            except Exception as e:
                log_error(f"Error merging research: {e}")

        with open("data/research.json", 'w', encoding='utf-8') as f:
            json.dump(self.research, f, indent=4, ensure_ascii=False)

        # General info (often static or changing in place)
        full_general = self._merge_and_save("data/general.json", self.general, "title")
        with open("data/general.json", 'w', encoding='utf-8') as f:
            json.dump(full_general, f, indent=4, ensure_ascii=False)

        # Merge and Save News
        full_news = self._merge_and_save("data/news.json", self.news, "url")
        with open("data/news.json", 'w', encoding='utf-8') as f:
            json.dump(full_news, f, indent=4, ensure_ascii=False)

        log_info(f"Saved (Merged) {len(full_events)} events, {len(full_people)} people, {len(full_news)} news.")
        log_info(f"Saved {len(self.research)} research categories, {len(full_general)} general items.")
        
        # Auto-update Graph
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
    scraper.scrape_news()
    scraper.save_to_json()
