import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

from src.utils.logger import log_info, log_error
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

    def __init__(self):
        self.events = []
        self.people = []
        self.research = []
        self.general = []
        self.general = []
        self.important_urls = self.load_important_urls()

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
        """Scrapes multiple sources for event links."""
        for source_url in self.EVENT_SOURCES:
            log_info(f"Starting scrape of {source_url}")
            try:
                response = requests.get(source_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                event_links = soup.find_all('a', href=True)
                for link in event_links:
                    href = link['href']
                    text = link.get_text(strip=True)
                    
                    is_event_link = False
                    # Look for links that contain "/event/" or specifically name an activity
                    lower_href = href.lower()
                    if "/event/" in href:
                        is_event_link = True
                    elif any(kw in lower_href for kw in ["talk-", "workshop-", "conference-", "colloquium-", "seminar-", "reading-group"]):
                        if ".html" in href:
                            is_event_link = True

                    if is_event_link:
                        # Construct full URL correctly
                        if href.startswith("http"):
                            full_url = href
                        elif href.startswith("/"):
                            full_url = f"{self.BASE_URL}{href}"
                        else:
                            # Relative to the source URL
                            base_path = source_url.rsplit('/', 1)[0]
                            full_url = f"{base_path}/{href}".replace("/./", "/")
                        
                        if full_url not in [e['url'] for e in self.events]:
                            title = text
                            if not title:
                                title = href.split('/')[-1].replace('.html', '').replace('-', ' ').title()
                            
                            self.events.append({
                                "title": title,
                                "url": full_url,
                                "scraped_at": datetime.now().isoformat()
                            })
            except Exception as e:
                log_error(f"Error scraping {source_url}: {e}")
        
        log_info(f"Found {len(self.events)} unique event links in total.")
        
        # Now scrape details for all found events
        for event in self.events:
            self.scrape_event_details(event)
            
        return self.events

    def scrape_event_details(self, event):
        """Scrapes details for a single event."""
        log_info(f"Scraping details for: {event['title']}")
        try:
            response = requests.get(event['url'])
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content - looking for main content area
            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                # Remove navigation/unwanted parts if any
                event['description'] = main_content.get_text(separator='\n', strip=True)
            else:
                event['description'] = soup.get_text(separator='\n', strip=True)
            
            # Clean up the description
            event['description'] = self._clean_text(event['description'])
            
            # Try to find specific metadata (Date, Time, Location)
            # This often lives in specific dl/dt/dd tags or tables
            metadata = {}
            for dl in soup.find_all('dl'):
                for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
                    key = dt.get_text(strip=True).lower().replace(':', '')
                    val = dd.get_text(strip=True)
                    metadata[key] = val
            
            event['metadata'] = metadata
            
        except Exception as e:
            log_error(f"Error scraping event details for {event['url']}: {e}")

    def scrape_people(self):
        """Scrapes the people directory and individual profiles."""
        # Use important URLs if available, otherwise default
        sources = [u for u in self.important_urls if "people" in u]
        if not sources:
            sources = self.PEOPLE_URLS

        for people_url in sources:
            log_info(f"Starting scrape of people from {people_url}")
            try:
                response = requests.get(people_url)
                response.raise_for_status()
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

            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Name usually in H1
            name_elem = soup.find('h1')
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Person"
            
            # Main content
            main_content = soup.find('div', id='r-main') or soup.find('main')
            description = ""
            metadata = {}

            if main_content:
                description = main_content.get_text(separator=' ', strip=True)
                
                # Extract contact info
                emails = [a.get_text() for a in main_content.find_all('a') if "@" in a.get_text()]
                if emails:
                    metadata['email'] = emails[0]
                
                # Extract Research Interests specifically
                # Look for "Research interests" header
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

            response = requests.get(self.RESEARCH_URL)
            response.raise_for_status()
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
            response = requests.get(url)
            response.raise_for_status()
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
            response = requests.get(home_url)
            response.raise_for_status()
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
            response = requests.get(url)
            response.raise_for_status()
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

    def save_to_json(self):
        """Saves scraped data to JSON files."""
        os.makedirs("data", exist_ok=True)
        
        with open("data/raw_events.json", 'w', encoding='utf-8') as f:
            json.dump(self.events, f, indent=4, ensure_ascii=False)
        
        with open("data/people.json", 'w', encoding='utf-8') as f:
            json.dump(self.people, f, indent=4, ensure_ascii=False)
            
        with open("data/research.json", 'w', encoding='utf-8') as f:
            json.dump(self.research, f, indent=4, ensure_ascii=False)

        with open("data/general.json", 'w', encoding='utf-8') as f:
            json.dump(self.general, f, indent=4, ensure_ascii=False)
            
        log_info(f"Saved {len(self.events)} events, {len(self.people)} people, {len(self.research)} research items, {len(self.general)} general items.")
        
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
    scraper.save_to_json()
