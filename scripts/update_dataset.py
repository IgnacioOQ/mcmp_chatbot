
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.mcmp_scraper import MCMPScraper
from src.utils.logger import log_info

def main():
    log_info("Starting Full Dataset Update Protocol...")
    
    # 1. Scrape All Data
    scraper = MCMPScraper()
    
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
    
    # 2. Save Data (This triggers graph build now)
    log_info("Saving data and building graph...")
    scraper.save_to_json()
    
    log_info("Update Protocol Complete.")

if __name__ == "__main__":
    main()
