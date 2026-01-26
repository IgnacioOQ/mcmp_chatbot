import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
from src.utils.logger import log_info, log_error

class MCMPScraper:
    BASE_URL = "https://www.philosophie.lmu.de"
    EVENT_SOURCES = [
        f"{BASE_URL}/mcmp/en/latest-news/events-overview/index.html",
        f"{BASE_URL}/mcmp/en/events/index.html",
        f"{BASE_URL}/mcmp/en/index.html"
    ]
    PEOPLE_URL = f"{BASE_URL}/mcmp/en/people/index.html"
    RESEARCH_URL = f"{BASE_URL}/mcmp/en/research/index.html"

    def __init__(self):
        self.events = []
        self.people = []
        self.research = []
        self.general = []

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
        """Scrapes the people directory."""
        log_info(f"Starting scrape of {self.PEOPLE_URL}")
        try:
            response = requests.get(self.PEOPLE_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Based on the view_content_chunk, people are listed with links to contact pages
            # We look for links inside the academic staff section (or general list)
            # A good heuristic is links containing "/people/contact-page/"
            
            person_links = soup.find_all('a', href=True)
            for link in person_links:
                href = link['href']
                if "/people/contact-page/" in href or "/faculty/" in href or "/staff/" in href:
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    name = link.get_text(strip=True)
                    
                    if full_url not in [p['url'] for p in self.people] and name:
                        self.people.append({
                            "name": name,
                            "url": full_url,
                            "type": "person",
                            "scraped_at": datetime.now().isoformat()
                        })
            
            log_info(f"Found {len(self.people)} people profiles.")
            return self.people
        except Exception as e:
            log_error(f"Error scraping people: {e}")
            return []

    def scrape_research(self):
        """Scrapes the research projects, including subpages."""
        log_info(f"Starting scrape of {self.RESEARCH_URL}")
        try:
            # 1. Scrape main research page
            response = requests.get(self.RESEARCH_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find links to specific research subpages
            subpage_links = set()
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/research/" in href and href != self.RESEARCH_URL:
                     # Filter out non-content links if possible, or just strict path checking
                     # The ML page is .../mcmp/en/research/philosophy-of-machine-learning/
                     if "/mcmp/en/research/" in href and "publications" not in href:
                         full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                         subpage_links.add(full_url)

            # Ensure the specific ML page requested is included even if discovery fails
            ml_page = f"{self.BASE_URL}/mcmp/en/research/philosophy-of-machine-learning/"
            subpage_links.add(ml_page)

            # 2. Scrape each subpage
            for url in subpage_links:
                try:
                    self._scrape_single_research_page(url)
                except Exception as e:
                    log_error(f"Failed to scrape research subpage {url}: {e}")

            log_info(f"Found {len(self.research)} research items/pages.")
            return self.research
        except Exception as e:
            log_error(f"Error scraping research: {e}")
            return []

    def _scrape_single_research_page(self, url):
        """Helper to scrape a specific research page."""
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get title
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Research Project"
        
        # Get main content
        main_content = soup.find('div', id='r-main') or soup.find('main')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            # Remove navigation noise if possible (simple heuristic: takes long text)
            
            self.research.append({
                "title": title,
                "description": text[:5000], # Limit length to avoid massive context
                "url": url,
                "type": "research",
                "scraped_at": datetime.now().isoformat()
            })

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

if __name__ == "__main__":
    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.scrape_people()
    scraper.scrape_research()
    scraper.scrape_general()
    scraper.scrape_reading_groups()
    scraper.save_to_json()
