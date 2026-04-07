
import sys
import os
import argparse
import json
from datetime import datetime, timedelta

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scrapers.mcmp_scraper import MCMPScraper
from src.utils.logger import log_info

_OFFERINGS_THROTTLE_DAYS = 30
_LOG_PATH = "data/scraping_logs.json"


def should_scrape_academic_offerings(force: bool = False) -> bool:
    """Returns True if offerings haven't been scraped in the last 30 days, or if forced."""
    if force:
        return True
    if not os.path.exists(_LOG_PATH):
        return True
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            logs = json.load(f)
        for entry in reversed(logs):
            if "academic_offerings" in entry.get("changes", {}):
                last = datetime.fromisoformat(entry["timestamp"])
                return datetime.now() - last > timedelta(days=_OFFERINGS_THROTTLE_DAYS)
    except Exception:
        pass
    return True  # scrape if no prior record found


def main():
    parser = argparse.ArgumentParser(description="Update MCMP chatbot datasets.")
    parser.add_argument(
        "--scrape-offerings",
        action="store_true",
        help="Force scrape academic offerings regardless of last-scraped date (otherwise throttled to once per 30 days).",
    )
    args = parser.parse_args()

    log_info("Starting Full Dataset Update Protocol...")

    scraper = MCMPScraper()
    scraper.scrape_events()
    scraper.scrape_people()
    scraper.scrape_research()
    scraper.scrape_general()
    scraper.scrape_reading_groups()

    if should_scrape_academic_offerings(force=args.scrape_offerings):
        log_info("Scraping academic offerings (throttle window elapsed or forced)...")
        scraper.scrape_academic_offerings()
    else:
        log_info(f"Skipping academic offerings scrape (last scraped within {_OFFERINGS_THROTTLE_DAYS} days). Use --scrape-offerings to force.")

    scraper.save_to_json()

    log_info("Update Protocol Complete.")

if __name__ == "__main__":
    main()
