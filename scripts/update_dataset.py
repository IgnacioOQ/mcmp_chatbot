
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.mcmp_scraper import MCMPScraper
from src.scrapers.html_mcmp_scraper import HTMLMCMPScraper
from src.utils.logger import log_info

def merge_datasets(primary_list, secondary_list, unique_key="url"):
    """Merges secondary list into primary list, avoiding duplicates by unique_key.

    unique_key can be a field name (str) or a callable that takes an item and returns a key.
    """
    def get_key(item):
        if callable(unique_key):
            return unique_key(item)
        return item.get(unique_key)

    seen_keys = {get_key(item) for item in primary_list if get_key(item)}

    for item in secondary_list:
        k = get_key(item)
        if k and k not in seen_keys:
            primary_list.append(item)
            seen_keys.add(k)

    return primary_list

def main():
    log_info("Starting Full Dataset Update Protocol (with Parallel HTML Scraper)...")
    
    # 1. Scrape All Data with Primary Scraper (MCMPScraper)
    scraper = MCMPScraper()
    
    log_info("--- Running Primary Scraper ---")
    log_info("Scraping Events...")
    scraper.scrape_events()
    log_info("Scraping People...")
    scraper.scrape_people()
    log_info("Scraping Research...")
    scraper.scrape_research()
    log_info("Scraping General Info...")
    scraper.scrape_general()
    log_info("Scraping Reading Groups...")
    scraper.scrape_reading_groups()

    # 2. Scrape All Data with Secondary Scraper (HTMLMCMPScraper)
    html_scraper = HTMLMCMPScraper()
    
    log_info("--- Running Secondary HTML Scraper ---")
    log_info("Scraping Events (HTML)...")
    html_scraper.scrape_events()
    log_info("Scraping People (HTML)...")
    html_scraper.scrape_people()
    log_info("Scraping Research (HTML)...")
    html_scraper.scrape_research()
    log_info("Scraping General Info (HTML)...")
    html_scraper.scrape_general()
    log_info("Scraping Reading Groups (HTML)...")
    html_scraper.scrape_reading_groups()

    # 3. Merge Datasets
    log_info("--- Merging Datasets ---")
    scraper.events = merge_datasets(scraper.events, html_scraper.events)
    scraper.people = merge_datasets(scraper.people, html_scraper.people)
    # Research has a different structure (categories -> items)
    # Since it's deterministic based on URLs, merging top-level is sufficient for now,
    # but theoretically it might need deep merging if we were changing categories. 
    # For now, we favor primary structure but we could also add missing categories.
    scraper.research = merge_datasets(scraper.research, html_scraper.research, unique_key="id")
    scraper.general = merge_datasets(
        scraper.general, html_scraper.general,
        unique_key=lambda x: f"{x.get('url', '')}_{x.get('title', '')}"
    )

    # 4. Save Data (This triggers graph build now)
    log_info("Saving merged data and building graph...")
    scraper.save_to_json()
    
    log_info("Update Protocol Complete.")

if __name__ == "__main__":
    main()
