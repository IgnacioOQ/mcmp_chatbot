import json
import os
from datetime import datetime
import time

from src.utils.logger import log_info, log_error
from src.scrapers.base_scraper import BaseMCMPScraper

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


class MCMPScraper(BaseMCMPScraper):
    """
    Primary MCMP scraper.

    Uses Selenium to handle the dynamic 'Load more' button on the events-overview
    page, then falls back to static scraping for all other sources. Inherits all
    shared scraping logic from BaseMCMPScraper. Owns data persistence (save_to_json)
    and change logging (_log_changes).
    """

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Events scraping (Selenium + static fallback)
    # ------------------------------------------------------------------

    def scrape_events(self):
        """Scrapes multiple sources for event links with exhaustive nested search.

        Uses Selenium for pages with dynamic 'Load more' buttons (like events-overview).
        Falls back to requests.get() for other pages.
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
        else:
            log_info("No changes detected in datasets.")

    def _accumulate(self, new_data, file_path, key):
        """Merge new_data into existing file: update matching entries, add new ones, never remove.

        Args:
            new_data: Freshly scraped list of items.
            file_path: Path to the existing JSON file on disk.
            key: Field name (str) or callable used as the unique identifier.
        Returns:
            Merged list with all existing entries preserved.
        """
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
        are preserved as-is. This ensures the dataset only grows over time.
        """
        os.makedirs("data", exist_ok=True)

        self.events = self._accumulate(self.events, "data/raw_events.json", "url")
        self.people = self._accumulate(self.people, "data/people.json", "url")
        self.research = self._accumulate(self.research, "data/research.json", "id")
        self.general = self._accumulate(
            self.general, "data/general.json",
            lambda x: f"{x.get('url', '')}_{x.get('title', '')}",
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

        log_info(
            f"Saved {len(self.events)} events, {len(self.people)} people, "
            f"{len(self.research)} research items, {len(self.general)} general items."
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
