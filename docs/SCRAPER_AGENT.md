# Event Scraper Implementation Plan
- status: active
- type: guideline
<!-- content -->

This document defines the implementation plan for enhancing the MCMP event scraper to perform exhaustive nested searches and extract complete event details including abstracts.

## Website Structure

### Event Sources
1. **Events Overview** (Primary): `https://www.philosophie.lmu.de/mcmp/en/latest-news/events-overview/`
2. **Events Page**: `https://www.philosophie.lmu.de/mcmp/en/events/`
3. **Homepage**: `https://www.philosophie.lmu.de/mcmp/en/`

### DOM Structure
- **Listing pages**: Events are in `<a>` tags with class `.filterable-list__list-item-link.is-events`
- **No pagination**: All events load on a single page
- **Individual event pages** contain structured sections:
  - `<h1>` with speaker/event name (e.g., "Talk: Simon Saunders (Oxford)")
  - `<h2>` labels for "Date:", "Location:", "Title:", "Abstract:"
  - Content in `.rte__content` divs or `<address>` tags

## Implementation Details

### 1. Event Discovery
Add the events-overview URL to sources:
```python
EVENT_SOURCES = [
    f"{BASE_URL}/mcmp/en/latest-news/events-overview/index.html",
    f"{BASE_URL}/mcmp/en/events/index.html",
    f"{BASE_URL}/mcmp/en/index.html"
]
```

Use CSS class selector for reliable event detection:
```python
event_links = soup.select('a.filterable-list__list-item-link.is-events')
```

### 2. Deduplication
Use URL as unique identifier:
```python
seen_urls = set()
for link in event_links:
    url = self._normalize_url(link['href'])
    if url not in seen_urls:
        seen_urls.add(url)
        # ... add event
```

### 3. Event Details Extraction
Parse structured fields from individual pages:

```python
def scrape_event_details(self, event):
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find labeled sections
    for h2 in soup.find_all('h2'):
        label = h2.get_text(strip=True).rstrip(':').lower()
        content_elem = h2.find_next_sibling()
        
        if label == 'title':
            event['talk_title'] = content_elem.get_text(strip=True)
        elif label == 'abstract':
            event['abstract'] = self._extract_section_content(h2)
        elif label == 'date':
            event['metadata']['date'] = self._parse_date(content_elem)
    
    # Location from address tag
    address = soup.find('address')
    if address:
        event['metadata']['location'] = address.get_text(' ', strip=True)
```

### 4. Output Schema
```json
{
    "title": "Talk: Simon Saunders (Oxford)",
    "url": "https://...",
    "scraped_at": "2026-01-31T...",
    "talk_title": "Bell inequality violation is evidence for many worlds",
    "abstract": "Given two principles (a) no action-at-a-distance...",
    "metadata": {
        "date": "2026-02-04",
        "year": 2026,
        "month": "February",
        "time_start": "4:00 pm",
        "location": "Ludwigstr. 31 Ground floor, room 021, 80539 München",
        "speaker": "Simon Saunders (Oxford)"
    }
}
```

## Verification Checklist
- [ ] All events have `abstract` field (if available on source)
- [ ] `talk_title` is separate from main `title`
- [ ] `metadata.location` contains only address
- [ ] No duplicate URLs
- [ ] Dates parsed to ISO format
