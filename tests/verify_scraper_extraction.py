
import sys
import os
import json
import logging

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.scrapers.mcmp_scraper import MCMPScraper

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

def verify_extraction():
    scraper = MCMPScraper()
    
    # Test Case 1: Hannes Leitgeb (Standard Profile)
    url1 = "https://www.philosophie.lmu.de/mcmp/en/people/contact-page/hannes-leitgeb-4769c328.html"
    print(f"Scraping {url1}...")
    scraper._scrape_single_person_page(url1)
    
    person1 = scraper.people[-1]
    print(json.dumps(person1, indent=4, ensure_ascii=False))
    
    # Test Case 2: Conrad Friedrich (Has Website?)
    url2 = "https://www.philosophie.lmu.de/mcmp/en/people/contact-page/friedrich-conrad-65ec0395.html"
    print(f"Scraping {url2}...")
    scraper._scrape_single_person_page(url2)
    
    person2 = scraper.people[-1]
    print(json.dumps(person2, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    verify_extraction()
