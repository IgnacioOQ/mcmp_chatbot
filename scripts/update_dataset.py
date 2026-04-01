
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.mcmp_scraper import MCMPScraper
from src.utils.logger import log_info

def main():
    log_info("Starting Full Dataset Update Protocol...")

    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.scrape_people()
    scraper.scrape_research()
    scraper.scrape_general()
    scraper.scrape_reading_groups()
    scraper.save_to_json()

    log_info("Update Protocol Complete.")

if __name__ == "__main__":
    main()
