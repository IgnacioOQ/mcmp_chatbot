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

    def __init__(self):
        self.events = []

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
                    # Look for links that contain "/event/" or specifically name an event
                    if "/event/" in href:
                        is_event_link = True
                    elif "talk-" in href.lower() or "workshop-" in href.lower() or "conference-" in href.lower():
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

    def save_to_json(self, filepath="data/raw_events.json"):
        """Saves the scraped events to a JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.events, f, indent=4, ensure_ascii=False)
        log_info(f"Saved {len(self.events)} events to {filepath}")

if __name__ == "__main__":
    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.save_to_json()
