import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.scrapers.mcmp_scraper import MCMPScraper

# Sample HTML content for mocking
SAMPLE_EVENTS_HTML = """
<html>
<body>
    <div id="r-main">
        <a href="http://example.com/event/1">Event 1</a>
        <a href="/event/2">Event 2</a>
        <a href="talk-sample.html">Talk: Sample</a>
    </div>
</body>
</html>
"""

SAMPLE_PEOPLE_HTML = """
<html>
<body>
    <div id="r-main">
        <a href="contact-page/doe-john/index.html">Doe, John</a>
    </div>
</body>
</html>
"""

@pytest.fixture
def scraper():
    return MCMPScraper()

def test_init(scraper):
    assert scraper.events == []
    assert scraper.people == []
    assert scraper.BASE_URL == "https://www.philosophie.lmu.de"

@patch('requests.get')
def test_scrape_events(mock_get, scraper):
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_EVENTS_HTML
    mock_get.return_value = mock_response

    # Run scraping
    events = scraper.scrape_events()

    # Assertions
    assert len(events) > 0
    # Check that URLs are normalized
    assert any("http://example.com/event/1" in e['url'] for e in events)
    # Check that relative URLs are handled (logic in scraper)
    
@patch('requests.get')
def test_scrape_people(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_PEOPLE_HTML
    mock_get.return_value = mock_response

    # We need to mock the recursive call or the list of URLs logic
    # The scraper uses scraper.PEOPLE_URLS
    
    # Let's mock _scrape_single_person_page to avoid recursive complexity in this unit test
    with patch.object(scraper, '_scrape_single_person_page') as mock_single:
        scraper.scrape_people()
        # Verify it found the link and tried to scrape it
        assert mock_single.call_count == 1
        # Check argument
        args, _ = mock_single.call_args
        assert "contact-page/doe-john/index.html" in args[0]

def test_merge_and_save(scraper):
    """Test the data merging logic."""
    # Setup mock existing data
    existing_data = [
        {"url": "http://example.com/old", "title": "Old Event"},
        {"url": "http://example.com/update", "title": "Old Title"}
    ]
    
    # Setup new scraped data
    new_data = [
        {"url": "http://example.com/update", "title": "New Title"},
        {"url": "http://example.com/new", "title": "New Event"}
    ]
    
    # Create a temporary file with existing data
    import json
    import os
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
        json.dump(existing_data, tmp)
        tmp_path = tmp.name
        
    try:
        # Run merge logic
        merged = scraper._merge_and_save(tmp_path, new_data, key_field="url")
        
        # Verify results
        assert len(merged) == 3
        
        # Convert to dict for easier checking
        merged_dict = {item['url']: item for item in merged}
        
        # 1. Old preserved
        assert "http://example.com/old" in merged_dict
        assert merged_dict["http://example.com/old"]["title"] == "Old Event"
        
        # 2. Update overwrites old
        assert "http://example.com/update" in merged_dict
        assert merged_dict["http://example.com/update"]["title"] == "New Title"
        
        # 3. New added
        assert "http://example.com/new" in merged_dict
        assert merged_dict["http://example.com/new"]["title"] == "New Event"

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
