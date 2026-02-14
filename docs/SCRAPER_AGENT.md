# Event Scraper Implementation Guide
- status: active
- type: guideline
<!-- content -->

This document defines the implementation patterns for the MCMP event scraper, including critical lessons learned from production usage.

---

## Critical: Dynamic Loading

> [!CAUTION]
> The events-overview page uses a **"Load more" button** to dynamically load events. Static `requests.get()` only captures 16 of 53+ events.

### Problem
- Initial page load shows ~16 events
- Remaining events load via JavaScript when clicking "Load more"
- Button class: `button.filterable-list__load-more`
- Requires 4+ clicks to reveal all events

### Solution: Selenium
```python
def _fetch_events_with_selenium(self, url):
    driver = webdriver.Chrome(options=headless_options)
    driver.get(url)
    
    # Click "Load more" until it disappears
    while True:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button.filterable-list__load-more")
            if btn.is_displayed():
                btn.click()
                time.sleep(1)
            else:
                break
        except NoSuchElementException:
            break
    
    # Now extract all event links
    links = driver.find_elements(By.CSS_SELECTOR, "a.filterable-list__list-item-link.is-events")
```

**Dependencies**: `selenium`, `webdriver-manager`

---

## Website Structure

### Event Sources
1. **Events Overview** (Primary): `https://www.philosophie.lmu.de/mcmp/en/latest-news/events-overview/` ⚠️ Dynamic
2. **Events Page**: `https://www.philosophie.lmu.de/mcmp/en/events/`
3. **Homepage**: `https://www.philosophie.lmu.de/mcmp/en/`

### DOM Structure
- **Listing pages**: Events in `<a>` tags with class `.filterable-list__list-item-link.is-events`
- **Individual event pages**:
  - `<h1>` with speaker/event name
  - `<h2>` labels for "Date:", "Location:", "Title:", "Abstract:"
  - Location in `<address>` tag

---

## Critical: UTF-8 Encoding

> [!CAUTION]
> The MCMP website serves UTF-8 content (smart quotes like `'`, em dashes, etc.), but `requests` may guess the wrong encoding from HTTP headers, causing **mojibake** (e.g., `'` → `â€™`).

### Problem
- `requests` defaults to `ISO-8859-1` for `text/html` when the server doesn't declare `charset=utf-8`
- UTF-8 multi-byte characters (smart quotes, accented names) decode as garbage

### Solution: `_get()` helper
All HTTP requests go through `self._get(url)`, which forces `response.encoding = 'utf-8'` before `response.text` is accessed:
```python
def _get(self, url):
    """Wrapper around requests.get that forces UTF-8 encoding."""
    response = requests.get(url)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response
```

> [!IMPORTANT]
> **Never call `requests.get()` directly** in scraping methods. Always use `self._get()`.

---

## Incremental Scraping (Backward Compatibility)

The scraper preserves historical data across runs using `_merge_and_save()`:
- **Events and People**: Merged by URL key. Records from previous scrapes that no longer appear on the website are **retained**. Only matching URLs get updated.
- **Research and General**: **Overwritten** each run (structural merge is too complex for hierarchical category data).

This ensures a growing knowledge base where past events remain queryable even after they leave the website.

---

## Implementation Patterns

### 1. Deduplication (URL-based)
```python
seen_urls = set()
for link in event_links:
    url = self._normalize_url(link['href'])
    if url not in seen_urls:
        seen_urls.add(url)
```

### 2. Event Details Extraction
```python
# Labeled sections
for h2 in soup.find_all('h2'):
    label = h2.get_text(strip=True).rstrip(':').lower()
    if label == 'abstract':
        event['abstract'] = self._extract_section_content(h2)

# Location from address tag
address = soup.find('address')
if address:
    event['metadata']['location'] = address.get_text(' ', strip=True)
```

### 3. Date Parsing
```python
# "4 February 2026" → "2026-02-04"
match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
```

---

## Output Schema
```json
{
    "title": "Talk: Simon Saunders (Oxford)",
    "url": "https://...",
    "talk_title": "Bell inequality violation is evidence for many worlds",
    "abstract": "Given two principles (a) no action-at-a-distance...",
    "metadata": {
        "date": "2026-02-04",
        "time_start": "4:00 pm",
        "location": "Ludwigstr. 31 Ground floor, room 021",
        "speaker": "Simon Saunders (Oxford)"
    }
}
```

---

## People Scraper Implementation

### Sources
- **People Index**: `https://www.philosophie.lmu.de/mcmp/en/people/`
- **Profile Pages**: Individual pages linked from the index (e.g., `/people/contact-page/...`)

### DOM Structure (Profile Page)

| Field | Selector / Logic | Notes |
|-------|------------------|-------|
| **Name** | `h1.header-person__name` | Fallback to `h1` |
| **Position** | `p.header-person__job` | e.g., "Doctoral Fellow" |
| **Org Unit** | `p.header-person__department` | e.g., "Chair of Philosophy of Science" |
| **Email** | `a.header-person__contentlink.is-email` | Strip "Send an email", check `mailto:` |
| **Phone** | `a.header-person__contentlink.is-phone` | |
| **Room** | `div.header-person__detail_area p` | **CRITICAL**: Exclude text containing "Room finder" |
| **Image** | `img.picture__image` | Get `src` attribute |
| **Website** | `a` with text "Personal website" | |
| **Publications** | `h2` "Selected publications" | Parse sibling `ul` or `ol` lists |

### Output Schema
```json
{
    "name": "Dr. Conrad Friedrich",
    "url": "https://...",
    "description": "Personal information...",
    "metadata": {
        "position": "Postdoctoral fellow",
        "organizational_unit": "MCMP",
        "email": "Conrad.Friedrich@lmu.de",
        "office_address": "Ludwigstr. 31",
        "room": "Room 225",
        "website": "https://conradfriedrich.github.io/",
        "image_url": "https://...",
        "selected_publications": ["Pub 1", "Pub 2"]
    }
}
```

---

## Verification
- [x] All 53+ events captured
- [x] Abstracts extracted from individual pages
- [x] No duplicate URLs
- [x] Dates in ISO format
- [x] UTF-8 encoding enforced (no mojibake in smart quotes/accented characters)
- [x] Past events/people preserved across scraper runs (incremental merge)
