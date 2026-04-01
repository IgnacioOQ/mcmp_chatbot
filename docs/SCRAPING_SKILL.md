# Web Scraping Skill Reference
- status: active
- type: agent_skill
- id: scraping-skill
- last_checked: 2026-04-01
- context_dependencies: {"conventions": "docs/MD_CONVENTIONS.md", "mcmp_scraper": "docs/SCRAPER_AGENT.md", "html_scraping": "docs/HTML_SCRAPING_SKILL.md"}
<!-- content -->

A consolidated reference for web scraping patterns used across this project. Covers both static HTML and dynamic (Selenium) scraping, with lessons learned from the MCMP website, `ayore.org` (trilingual WordPress/WPML), and `bible.com`.

---

## Core Principle: Find the HTML Indicator
- status: active
- type: context
- id: scraping-skill.html-indicator
<!-- content -->

Every piece of target content has an **HTML indicator** — a CSS class, attribute, tag structure, or pattern that uniquely identifies it. The scraper's job is to locate that indicator and extract the surrounding data.

**How to find indicators:**
1. Open DevTools → Inspect the element you want
2. Look for a **unique class or attribute** on the element or its container
3. Verify it is stable (not randomly generated — avoid Tailwind hashes, React IDs)
4. Confirm it does not appear in unrelated parts of the page

| Good indicators | Bad indicators |
| :--- | :--- |
| `class="entry-content"` (WordPress main div) | Generic `<div>` or `<p>` without a class |
| `class="wpml-ls-item-en"` (WPML language switcher) | Positional selectors like `nth-child(3)` |
| `<address>` tag (physical location) | Inline styles or dynamically generated names |
| `<h2>` with text `"Abstract:"` (labeled section) | |

---

## UTF-8 Encoding Enforcement
- status: active
- type: context
- id: scraping-skill.utf8
<!-- content -->

> [!CAUTION]
> `requests` may guess the wrong encoding from HTTP headers, causing **mojibake** (e.g. `Jürgen` → `JÃ¼rgen`). This affects names, addresses, and any non-ASCII text.

**Rule**: Never call `requests.get()` directly in scraping methods. Always use the `_fetch_page()` wrapper:

```python
import ftfy

def _fetch_page(self, url: str) -> BeautifulSoup:
    response = requests.get(url)
    response.raise_for_status()
    response.encoding = "utf-8"        # Force BEFORE accessing .text
    fixed = ftfy.fix_text(response.text)  # Repair residual issues
    return BeautifulSoup(fixed, "html.parser")
```

**Additional rules:**
- Never transliterate Unicode. Store `Jürgen` as `Jürgen`, not `Juergen`.
- Always use `ensure_ascii=False` when writing JSON: `json.dump(..., ensure_ascii=False)`.
- If existing JSON files contain mojibake, run `python scripts/fix_encoding.py` to repair them.

---

## Dynamic Content: Selenium for "Load More" Buttons
- status: active
- type: context
- id: scraping-skill.selenium
<!-- content -->

> [!CAUTION]
> Pages that use a JavaScript "Load more" button serve only a fraction of their content to static `requests.get()`. The MCMP events-overview page shows ~16 of 53+ events without Selenium.

**When to use Selenium**: when the page content changes in response to user interaction (clicks, scrolling, form submission) and cannot be loaded via a direct URL.

**Pattern: click until the button disappears**

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time

chrome_options = ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)
driver.get(url)

# Wait for initial content
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "a.filterable-list__list-item-link.is-events"))
)

max_clicks = 10  # Safety limit — prevents infinite loops
clicks = 0
while clicks < max_clicks:
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button.filterable-list__load-more")
        if btn.is_displayed():
            driver.execute_script("arguments[0].scrollIntoView();", btn)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            clicks += 1
        else:
            break
    except (NoSuchElementException, TimeoutException):
        break  # Button gone — all content loaded

driver.quit()
```

**Always wrap Selenium in try/finally** and call `driver.quit()` in the `finally` block to prevent zombie browser processes.

**Graceful fallback**: gate Selenium behind `SELENIUM_AVAILABLE` (set via a `try/except ImportError`). If unavailable, fall back to static HTML scraping.

---

## Static HTML Scraping with Requests + BeautifulSoup
- status: active
- type: context
- id: scraping-skill.static-html
<!-- content -->

When page content is fully rendered in the initial HTML response, static scraping is faster and more robust than Selenium.

**Typical workflow:**

```python
soup = self._fetch_page(url)                         # UTF-8 enforced
links = soup.select("a.filterable-list__list-item-link.is-events")  # CSS selector

# Fallback to heuristic matching if primary selector returns nothing
if not links:
    links = [a for a in soup.find_all("a", href=True) if self._is_event_link(a["href"])]
```

**Prefer CSS selectors** (`soup.select("...")`) over chained `find_all` calls when the target has a stable class. Use `find_all` + lambda for more complex conditional logic.

---

## URL Handling
- status: active
- type: context
- id: scraping-skill.url-handling
<!-- content -->

### Normalization to absolute URLs

```python
def _normalize_url(self, href, source_url):
    if href.startswith("http"):
        return href
    elif href.startswith("/"):
        return f"{self.BASE_URL}{href}"
    else:
        base_path = source_url.rsplit("/", 1)[0]
        return f"{base_path}/{href}".replace("/./", "/")
```

### Anchor-fragment filtering

Index pages contain navigation anchors (`#masthead`, `#faculty`) that share the section path but are not real content pages. Always drop them first:

```python
if "#" in href:
    continue
```

> [!CAUTION]
> Without this filter, `#masthead` links get collected as story URLs, scrape the section index page instead of a story, and produce bogus entries.

### URL deduplication

Use a `set` to deduplicate within a scraping session:

```python
seen_urls: set = set()
for link in links:
    url = self._normalize_url(link["href"], source_url)
    if url in seen_urls:
        continue
    seen_urls.add(url)
```

For cross-method deduplication (e.g., preventing a person profile from being scraped twice), maintain a persistent set on the instance: `self._scraped_person_urls: set = set()`. Check it with `if url in self._scraped_person_urls: return` — O(1) vs. the O(n) anti-pattern `if url in [p["url"] for p in self.people]`.

---

## Section Content Extraction
- status: active
- type: context
- id: scraping-skill.section-extraction
<!-- content -->

Many MCMP pages use labeled `<h2>` sections (e.g., `Abstract:`, `Date:`, `Title:`). Extract the content following a header by traversing siblings until the next header:

```python
def _extract_section_content(self, header_elem) -> str:
    content_parts = []
    sibling = header_elem.find_next_sibling()
    while sibling and sibling.name not in ["h1", "h2", "h3"]:
        text = sibling.get_text(" ", strip=True)
        if text:
            content_parts.append(text)
        sibling = sibling.find_next_sibling()
    return " ".join(content_parts).strip()
```

> [!CAUTION]
> **Loop placement bug**: When accumulating section content in a `while` loop and then appending a result dict, the `append` call must be placed **after** the while loop — not inside it. Placing it inside produces N duplicate entries with progressively more text per section. The correct structure is:
> ```python
> content = ""
> curr = header.find_next_sibling()
> while curr and curr.name not in ["h2", "h1"]:
>     content += curr.get_text(separator=" ", strip=True) + "\n"
>     curr = curr.find_next_sibling()
> if content.strip():                 # ← OUTSIDE the while loop
>     self.general.append({...})
> ```

---

## Date/Time Parsing
- status: active
- type: context
- id: scraping-skill.date-parsing
<!-- content -->

```python
import re

def _parse_date_time(self, date_text: str) -> dict:
    result = {}

    # "4 February 2026" → "2026-02-04"
    date_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_text)
    if date_match:
        day, month_name, year = date_match.groups()
        month_map = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        month_num = month_map.get(month_name.lower(), "01")
        result["date"] = f"{year}-{month_num}-{int(day):02d}"
        result["year"] = int(year)
        result["month"] = month_name

    # "4:00 pm" or "10:00 am – 12:00 pm"
    time_match = re.search(r"(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.IGNORECASE)
    if time_match:
        result["time_start"] = time_match.group(1).strip()

    end_time_match = re.search(r"-\s*(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.IGNORECASE)
    if end_time_match:
        result["time_end"] = end_time_match.group(1).strip()

    return result
```

Always import `re` at the **module level** — never inside a function body.

---

## People Profile Extraction (MCMP)
- status: active
- type: context
- id: scraping-skill.people-profiles
<!-- content -->

DOM selectors for MCMP individual profile pages:

| Field | Selector / Logic |
| :--- | :--- |
| Name | `h1.header-person__name` → fallback to `h1` |
| Position | `p.header-person__job` |
| Org Unit | `p.header-person__department` |
| Email | `a.header-person__contentlink.is-email` — strip "Send an email"; fallback to `mailto:` href |
| Phone | `a.header-person__contentlink.is-phone` |
| Room | `div.header-person__detail_area p` — match "Room" but **exclude** "Room finder" |
| Office address | Same area — match "Ludwigstr" or "Geschwister-Scholl" |
| Image | `img.picture__image` → `src` attribute |
| Website | `<a>` with text "Personal website" |
| Publications | `h2` "Selected publications" → `find_parent("div", class_="rte__content")` → `ol`/`ul` |

**Main content**: extract from `div.rte__content` divs inside `div#r-main`, skipping the publications section already captured above.

---

## Data Accumulation Policy
- status: active
- type: context
- id: scraping-skill.accumulation
<!-- content -->

> [!CAUTION]
> **Entries are NEVER removed from JSON datasets.** The scraper accumulates data over time. If an entry disappears from the website (e.g. "Load more" not triggered, page taken down), its record is preserved in the JSON file.

**Why**: the events-overview page requires Selenium to load all events. A static run only captures ~16 of 53+ events. Without accumulation, a static fallback run would wipe out all previously scraped events.

**How `_accumulate()` works:**

```python
def _accumulate(self, new_data, file_path, key):
    existing = json.loads(Path(file_path).read_text()) if Path(file_path).exists() else []
    def get_id(item):
        return key(item) if callable(key) else item.get(key)
    merged = {get_id(item): item for item in existing if get_id(item)}
    for item in new_data:
        item_id = get_id(item)
        if item_id:
            merged[item_id] = item   # update or add; existing entries without a match are kept
    return list(merged.values())
```

The `_log_changes()` method still records `"removed"` entries for auditing (absent from this scrape) but they are **not** deleted from the file.

---

## Multi-Language Scraping: WPML Pattern
- status: active
- type: context
- id: scraping-skill.wpml
<!-- content -->

`ayore.org` and many WordPress sites use **WPML** (WordPress Multilingual Plugin). WPML inserts a language switcher into every page that links to the exact equivalent URL in every other language.

> [!CAUTION]
> **Do NOT use positional pairing** (matching story #1 in ES with story #1 in EN by crawling index pages independently). Production result (2026-03-01): positional pairing was wrong for 13 of 14 stories on `relatos-personales`. Use the WPML switcher instead.

**WPML switcher HTML structure:**

```html
<div class="wpml-ls-statics-shortcode_actions wpml-ls ...">
  <ul>
    <li class="wpml-ls-item wpml-ls-item-en ...">
      <a href="https://ayore.org/culture/.../slug-en/" class="wpml-ls-link">
        <span class="wpml-ls-native" lang="en">English</span>
      </a>
    </li>
    <li class="wpml-ls-item wpml-ls-item-ayo ...">
      <a href="https://ayore.org/ayo/culture/.../slug-ayo/" class="wpml-ls-link">
        <span class="wpml-ls-native" lang="ayo">Ayoré</span>
      </a>
    </li>
  </ul>
</div>
```

> [!IMPORTANT]
> The switcher shows only the **other** languages — not the current page's language.

**Extract language URLs from the WPML switcher:**

```python
def extract_language_urls(soup) -> dict[str, str]:
    urls = {}
    switcher = soup.find("div", class_="wpml-ls")
    if not switcher:
        return urls
    for li in switcher.find_all("li", class_="wpml-ls-item"):
        span = li.find("span", class_="wpml-ls-native")
        a = li.find("a", class_="wpml-ls-link")
        if span and a:
            lang = span.get("lang")    # e.g. "en", "ayo"
            href = a.get("href")
            if lang and href:
                urls[lang] = href
    return urls
```

**Recommended crawl strategy:**
1. Crawl the ES index (most complete language) to get all story URLs
2. For each ES story page, call `extract_language_urls()` to get exact EN and AYO URLs
3. Store all three under a shared `story_id` (use the ES slug as canonical key)

---

## Linked-List Traversal
- status: active
- type: context
- id: scraping-skill.linked-list
<!-- content -->

When a website's content is structured as a sequence (e.g., chapters of a book), following "next page" links is more robust than hardcoding chapter counts or indexes.

**Pattern (bible.com chapters):**

1. Start at a known first URL (e.g., `GEN.1.AYORE`)
2. Parse the page's content
3. Find the `<a>` whose text contains `"Siguiente capítulo"` (next chapter)
4. Construct sibling-language URLs by swapping the version ID / suffix
5. Repeat until no next-chapter link exists

This guarantees only chapters present in the target translation are scraped.

**Safe resumption**: save progress after every item. On restart, load the existing file and skip entries whose `story_id` already exists:

```python
stories = json.loads(STORIES_PATH.read_text()) if STORIES_PATH.exists() else {}
if chapter_id in stories:
    continue   # already scraped, skip
# ... scrape ...
stories[chapter_id] = chapter_data
STORIES_PATH.write_text(json.dumps(stories, ensure_ascii=False, indent=2))
```

---

## Base Class Architecture
- status: active
- type: context
- id: scraping-skill.base-class
<!-- content -->

When two scrapers share the majority of their logic, extract a base class. Subclasses override only the method(s) that differ.

**Structure for the MCMP scrapers:**

```
BaseMCMPScraper                   # src/scrapers/base_scraper.py
├── __init__()                    # shared attributes + _scraped_person_urls set
├── _fetch_page()                 # UTF-8 + ftfy
├── _clean_text()
├── load_important_urls()
├── scrape_people()               # with anchor-fragment filter
├── _scrape_single_person_page()  # O(1) dedup via set
├── scrape_event_details()
├── _extract_section_content()
├── _parse_date_time()
├── scrape_research()
├── _scrape_single_research_page()
├── scrape_general()              # append OUTSIDE while loop
├── scrape_reading_groups()
├── _is_event_link()
└── _normalize_url()

MCMPScraper(BaseMCMPScraper)      # src/scrapers/mcmp_scraper.py
├── scrape_events()               # Selenium + static fallback
├── _fetch_events_with_selenium()
├── _accumulate()
├── _log_changes()
└── save_to_json()

HTMLMCMPScraper(BaseMCMPScraper)  # src/scrapers/html_mcmp_scraper.py
└── scrape_events()               # static HTML only
```

**Key design rules:**
- Base `__init__` initializes ALL shared state (events, people, research, general, `_scraped_person_urls`). Subclass `__init__` calls `super().__init__()` and nothing else.
- Module-level imports only — no `import x` inside function bodies.
- Constants (`BASE_URL`, `EVENT_SOURCES`, etc.) live on the base class.

---

## Verification Checklist
- status: active
- type: context
- id: scraping-skill.checklist
<!-- content -->

- [ ] UTF-8 enforced — no mojibake in names, addresses, or abstracts
- [ ] `_fetch_page()` wrapper used everywhere — no bare `requests.get()` calls
- [ ] Anchor fragment URLs (`#`) filtered out before processing
- [ ] URL deduplication via `set` (not list scan)
- [ ] Person deduplication via `self._scraped_person_urls` set
- [ ] `scrape_general()` appends outside the content-accumulation loop
- [ ] `import re` at module level, not inside `_parse_date_time()`
- [ ] Dates in ISO 8601 format (`YYYY-MM-DD`)
- [ ] JSON output uses `ensure_ascii=False`
- [ ] Accumulation policy preserved — `_accumulate()` never removes entries
- [ ] For WPML sites: language URLs sourced from switcher, not positional pairing
- [ ] For sequential content: safe resumption implemented (skip already-scraped IDs)
- [ ] Tests pass: `pytest tests/test_scraper.py -v`
