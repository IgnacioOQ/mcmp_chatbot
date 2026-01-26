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
        f"{BASE_URL}/mcmp/en/events/reading_groups/index.html", # Reading groups
        f"{BASE_URL}/mcmp/en/index.html"
    ]
    PEOPLE_URL = f"{BASE_URL}/mcmp/en/people/index.html"
    RESEARCH_URL = f"{BASE_URL}/mcmp/en/research/index.html"

    def __init__(self):
        self.events = []
        self.people = []
        self.research = []

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
        """Scrapes the research projects."""
        log_info(f"Starting scrape of {self.RESEARCH_URL}")
        try:
            response = requests.get(self.RESEARCH_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Projects seem to be listed under headers or specific sections
            # We'll look for generic project indicators or scrape the text structure
            
            # Simplified approach: Look for headers and following text blocks
            main_content = soup.find('div', id='r-main') or soup.find('main')
            if main_content:
                headers = main_content.find_all(['h2', 'h3'])
                for header in headers:
                    title = header.get_text(strip=True)
                    # Get the description (next sibling elements until next header)
                    description = ""
                    curr = header.find_next_sibling()
                    while curr and curr.name not in ['h2', 'h3']:
                        description += curr.get_text(separator=' ', strip=True) + "\n"
                        curr = curr.find_next_sibling()
                    
                    if len(description) > 50: # Only keep significant blocks
                         # Create a unique URL using anchor if possible, or fallback
                         anchor = title.lower().replace(" ", "-")
                         unique_url = f"{self.RESEARCH_URL}#{anchor}"
                         
                         self.research.append({
                            "title": title,
                            "description": description.strip(),
                            "url": unique_url, # Unique URL per project
                            "type": "research",
                            "scraped_at": datetime.now().isoformat()
                        })
            
            log_info(f"Found {len(self.research)} research items.")
            return self.research
        except Exception as e:
            log_error(f"Error scraping research: {e}")
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
            
        log_info(f"Saved {len(self.events)} events, {len(self.people)} people, {len(self.research)} research items.")

if __name__ == "__main__":
    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.scrape_people()
    scraper.scrape_research()
    scraper.save_to_json()
