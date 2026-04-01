from datetime import datetime

from src.utils.logger import log_info, log_error
from src.scrapers.base_scraper import BaseMCMPScraper


class HTMLMCMPScraper(BaseMCMPScraper):
    """
    Secondary MCMP scraper — static HTML only (no Selenium).

    Intended to run alongside MCMPScraper so that any events visible in the
    static HTML are captured even when Selenium is unavailable. All shared
    scraping logic is inherited from BaseMCMPScraper. Only scrape_events()
    is overridden here with a static-only implementation.
    """

    def __init__(self):
        super().__init__()

    def scrape_events(self):
        """Scrapes multiple sources for event links using only HTML/Requests."""
        seen_urls = set()

        for source_url in self.EVENT_SOURCES:
            log_info(f"HTML Scraper starting static scrape of {source_url}")
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

                    # Drop anchor fragments — not real pages
                    if "#" in href:
                        continue

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
                log_error(f"HTML Scraper error scraping {source_url}: {e}")

        log_info(f"HTML Scraper found {len(self.events)} unique event links in total.")

        for i, event in enumerate(self.events):
            log_info(f"Scraping event {i+1}/{len(self.events)}: {event['title']}")
            self.scrape_event_details(event)

        return self.events
