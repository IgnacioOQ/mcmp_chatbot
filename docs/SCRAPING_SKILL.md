# Web Scraping Implementation Guide
- status: active
- type: reference
- description: Consolidated web scraping reference: MCMP scraper (JSON API, Selenium, DOM selectors, accumulation), general HTML patterns, WPML multi-language, and bible.com traversal.
- injection: informational

<!-- content -->

This document consolidates scraping patterns for the MCMP chatbot project, covering general HTML scraping principles, MCMP-specific event/people/news scrapers, WPML multi-language handling (ayore.org), and bible.com traversal.

---

## Core Principle: Find the HTML Indicators

The key insight of web scraping is that **every piece of target content has an HTML indicator** — a CSS class, attribute, tag structure, or pattern that uniquely identifies it. The scraper's job is to locate that indicator and extract the data around it.

**How to find indicators:**
1. Open DevTools → Inspect the element you want to extract
2. Look for a **unique class or attribute** on the element or its container
3. Check whether the class/attribute is stable (not randomly generated, e.g. not Tailwind hashes or React IDs)
4. Verify it doesn't appear in unrelated parts of the page

**Examples of good indicators:**
- `class="entry-content"` → WordPress main content div
- `class="wpml-ls-item-en"` → WPML language switcher, English link
- `<address>` tag → physical location text
- `<h2>` with text "Abstract:" → labeled section header

**Examples of bad indicators:**
- Generic tags like `<div>`, `<p>` without class attributes
- Positional selectors like `nth-child(3)` — fragile if the page layout changes
- Inline styles or dynamically generated class names

---

## Critical: UTF-8 Encoding

> [!CAUTION]
> Many websites serve UTF-8 content (smart quotes like `'`, em dashes, accented characters), but `requests` may guess the wrong encoding from HTTP headers, causing **mojibake** (e.g., `'` → `â€™`). This is especially damaging for non-ASCII text like Ayoreo.

### Problem
- `requests` defaults to `ISO-8859-1` for `text/html` when the server doesn't declare `charset=utf-8`
- UTF-8 multi-byte characters (smart quotes, accented names) decode as garbage

### Solution: Always force UTF-8 before accessing `response.text`

**MCMP pattern (`_get()` helper):**
```python
def _get(self, url):
    """Wrapper around requests.get that forces UTF-8 encoding."""
    response = requests.get(url)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response
```

**General pattern (`fetch_page()` wrapper):**
```python
def fetch_page(url: str) -> BeautifulSoup | None:
    response = requests.get(url, headers={"User-Agent": "..."})
    response.raise_for_status()
    response.encoding = "utf-8"   # Force before .text is accessed
    return BeautifulSoup(response.text, "lxml")
```

> [!IMPORTANT]
> **Never call `requests.get()` directly** in scraping methods. Always use a wrapper that enforces UTF-8.

---

## Dynamic Content / Selenium

Some pages render content via JavaScript and require Selenium (or a JSON API bypass) to access the data.

### MCMP Events: JSON API Bypass
The MCMP events-overview page is JS-rendered via `LmuNewsboard.init()`. Rather than driving a browser, use the backing JSON API directly:
- **Endpoint**: `https://www.philosophie.lmu.de/mcmp/site_tech/json-newsboard/json-events-newsboard-en.json`
- Discovered from the `jsonUrl` attribute of the `LmuNewsboard` Vue component
- Returns **all events** reliably (54+) without Selenium

> [!NOTE]
> The JSON API bypasses JS rendering entirely, making Selenium optional for MCMP events.

### Selenium Fallback (Legacy)
The events-overview page uses a "Load more" button for dynamic loading. Selenium clicks it repeatedly to reveal all events. This is now only used as a supplement to the JSON API.

**Dependencies** (optional): `selenium`, `webdriver-manager`

### General Pattern
When a page is JS-rendered, inspect the network tab in DevTools before reaching for Selenium:
1. Look for a `data-*` attribute or component initialization that references a JSON endpoint
2. Fetch that endpoint directly — it typically returns structured data without any browser overhead
3. Fall back to Selenium only if no API endpoint is discoverable

---

## Static HTML Scraping: General Patterns

### 1. Filter Anchor Fragments Before Processing
Index pages often contain navigation links like `/section/#masthead` (back-to-top, logo anchors, etc.) that share the section path but are not real story pages. Always drop them first:

```python
# Drop anchor fragments — not real pages
if "#" in href:
    continue
```

> [!CAUTION]
> Without this filter, `#masthead` links get collected as story URLs, scrape the section index page instead of a story, and produce a bogus entry in the output.

### 2. URL Deduplication
```python
seen_urls = set()
for a_tag in soup.find_all("a", href=True):
    url = normalize_url(a_tag["href"], base_url)
    if url in seen_urls:
        continue
    seen_urls.add(url)
```

### 3. Language Guard (for no-prefix English URLs)
When crawling an English index that has no `/en/` prefix, AYO and ES sibling links will also contain the section path. Filter them out by checking the URL's language prefix:

```python
from src.scraping.utils import get_language_from_url

url_lang = get_language_from_url(href)  # returns "es", "ayo", "en", or None
if lang is None and url_lang is not None:
    continue  # skip ES/AYO links when collecting English pages
if lang is not None and url_lang != lang:
    continue  # skip links from other languages
```

### 4. Single Output File + Incremental Merge
Store all entries in **one JSON file** keyed by a stable ID. Running the scraper section by section builds up the file incrementally without overwriting previously scraped sections.

```python
STORIES_PATH = PROJECT_ROOT / "data" / "raw" / "ayoreoorg.json"

# Load existing stories
stories = json.loads(STORIES_PATH.read_text()) if STORIES_PATH.exists() else {}

# Merge new results (update or add by story_id)
for page_data in new_results:
    stories[page_data["story_id"]] = page_data

# Save back
STORIES_PATH.write_text(json.dumps(stories, ensure_ascii=False, indent=2))
```

**Do NOT save individual per-story JSON files.** One file is easier to load, version, and pass to downstream processing steps.

---

## URL Handling

### MCMP: Deduplication (URL-based)
```python
seen_urls = set()
for link in event_links:
    url = self._normalize_url(link['href'])
    if url not in seen_urls:
        seen_urls.add(url)
```

### ayore.org URL Structure
| Language | URL pattern | Notes |
| :--- | :--- | :--- |
| Spanish | `https://ayore.org/es/cultura/{section}/{slug}/` | Always present |
| English | `https://ayore.org/culture/{section}/{slug}/` | **No lang prefix** |
| Ayoré | `https://ayore.org/ayo/culture/{section}/{slug}/` | `ayo/` prefix |

> [!NOTE]
> AYO URLs often contain percent-encoded Ayoreo characters (e.g. `cotate-e-ye%cc%83ra-yu` where `%cc%83` = the ñ tilde). These are valid URLs; `requests` handles them correctly as long as you don't double-encode them.

---

## MCMP-Specific: Event Scraper

### Primary Source: JSON API
- **Endpoint**: `https://www.philosophie.lmu.de/mcmp/site_tech/json-newsboard/json-events-newsboard-en.json`
- Discovered from the `jsonUrl` attribute of the `LmuNewsboard` Vue component on the events-overview page
- Returns **all events** reliably (54+) without Selenium or dynamic page loading

### How It Works
1. **Fetch JSON index** from the API — returns all events with `id`, `date`, `dateEnd`, `link.href`, `link.text`
2. **Pre-populate metadata** from API data (`date`, `date_end` for multi-day events)
3. **Scrape individual pages** for full details (speaker, abstract, location, times)
4. **Fallback**: Selenium and static HTML scraping supplement the API for any events it might miss

### API Response Schema
```json
{
    "id": "9216",
    "categoryHeadline": "Event",
    "date": "2026-06-25T00:00:00.000Z",
    "dateEnd": "2026-06-26T00:00:00.000Z",
    "link": {
        "href": "https://...event/the-epistemology-of-medicine-92a34605.html",
        "text": "The Epistemology of Medicine"
    },
    "time": "",
    "topics": [],
    "description": ""
}
```

### DOM Structure (Individual Event Pages)
- `<h1>` with speaker/event name
- `<h2>` labels for "Date:", "Location:", "Title:", "Abstract:"
- Location in `<address>` tag

### Event Details Extraction
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

### Date Parsing
```python
# "4 February 2026" → "2026-02-04"
match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
```

### Output Schema (Events)
```json
{
    "title": "Talk: Simon Saunders (Oxford)",
    "url": "https://...",
    "talk_title": "Bell inequality violation is evidence for many worlds",
    "abstract": "Given two principles (a) no action-at-a-distance...",
    "metadata": {
        "date": "2026-02-04",
        "date_end": "2026-02-05",
        "time_start": "4:00 pm",
        "location": "Ludwigstr. 31 Ground floor, room 021",
        "speaker": "Simon Saunders (Oxford)"
    }
}
```

---

## MCMP-Specific: People Scraper

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

### Output Schema (People)
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

## MCMP-Specific: News Scraper

### Source
- **JSON API**: `https://www.philosophie.lmu.de/mcmp/site_tech/json-newsboard/json-news-newsboard-en.json`
- Discovered from the `data-` attributes of the `LmuNewsboard` Vue component on the news-overview page

> [!NOTE]
> The news-overview page (`/latest-news/news-overview/`) is fully JS-rendered via `LmuNewsboard.init()`. Static scraping sees no content. The JSON API endpoint bypasses this entirely.

### How It Works
1. **Fetch JSON index** from the API — returns a list of news items with `id`, `date`, `link.href`, `link.text`
2. **Scrape individual pages** for full content (`div.rte__content` or fallback to `main`)
3. **Store in `data/news.json`** with incremental merge (URL-keyed, like events/people)

### API Response Schema
```json
{
    "id": "11072",
    "categoryHeadline": "News",
    "date": "2026-02-02T14:07:38.628Z",
    "link": {
        "href": "https://...news/call-for-application-phd-student-mfx-b7a800fd.html",
        "text": "Call for Application: PhD student (m/f/x)"
    },
    "topics": [],
    "description": ""
}
```

### Output Schema (`data/news.json`)
```json
{
    "title": "Call for Application: PhD student (m/f/x)",
    "url": "https://...",
    "metadata": {
        "date": "2026-02-02",
        "category": "News"
    },
    "description": "Full text scraped from the individual news page...",
    "type": "news",
    "scraped_at": "2026-02-14T..."
}
```

### Content Types
- Job postings (PhD, postdoc, faculty positions)
- Calls for papers/abstracts
- Award announcements (Karl-Heinz Hoffmann Prize, Kurt Gödel Award)
- Publication announcements
- Partnership announcements

### MCP Tool
Exposed as `search_news(query)` — searches titles and descriptions. Separate from `get_events` since news and events are semantically different.

---

## MCMP-Specific: Accumulation Policy

The scraper preserves historical data across runs using `_merge_and_save()`:
- **Events and People**: Merged by URL key. Records from previous scrapes that no longer appear on the website are **retained**. Only matching URLs get updated.
- **Research and General**: **Overwritten** each run (structural merge is too complex for hierarchical category data).

This ensures a growing knowledge base where past events remain queryable even after they leave the website.

---

## MCMP-Specific: Dataset Size Tracking

> [!IMPORTANT]
> To monitor the growth of the knowledge base, agents must log the file sizes of the generated datasets into `AGENT_LOGS.md` after running the scraper.

### Logging Protocol
After successfully executing `scripts/update_dataset.py`, follow these steps:
1. Examine the file sizes of the primary datasets located in `data/`.
2. Inspect the JSON files to count the total number of top-level entries (e.g., number of events, number of people) in each. Compare this to the previous run to note if new entries were added.
3. Open `AGENT_LOGS.md` and locate the `## Dataset Size History` section.
4. Append a new entry with the current date, the sizes (in KB/MB), the exact entry counts, and a note indicating `(+X new)` if applicable.

Example format for `AGENT_LOGS.md`:
```markdown
### [YYYY-MM-DD]
- events.json: 85 KB (51 entries, +2 new)
- people.json: 210 KB (80 entries, +0 new)
- research.json: 45 KB (4 entries, +0 new)
- general.json: 12 KB (6 entries, +0 new)
- news.json: 30 KB (8 entries, +1 new)
```

---

## Multi-Language / WPML (ayore.org)

`ayore.org` (and many WordPress sites) use **WPML** (WordPress Multilingual Plugin) to serve the same content in multiple languages. WPML inserts a language switcher widget into each page that links to the exact equivalent URL in every other language.

### Why This Matters — Empirically Validated
**Do NOT rely on positional pairing** (matching story #1 in ES with story #1 in AYO by crawling index pages independently). This breaks silently if:
- A story exists in one language but not another
- Stories are listed in different orders per language
- New stories are added asynchronously

> [!CAUTION]
> **Production result (2026-03-01):** When scraping `relatos-personales` (14 stories), positional pairing produced the **wrong EN/AYO URL for 13 out of 14 stories**. The WPML switcher corrected every single one. Positional pairing is essentially useless for this site.

**Instead: use the WPML switcher on each scraped page** to get the exact URL mapping between language versions.

### WPML Language Switcher HTML
```html
<div class="wpml-ls-statics-shortcode_actions wpml-ls wpml-ls-legacy-list-horizontal">
  <ul>
    <li class="wpml-ls-slot-shortcode_actions wpml-ls-item wpml-ls-item-en wpml-ls-first-item wpml-ls-item-legacy-list-horizontal">
      <a href="https://ayore.org/culture/first-person-narratives/cotade-i-gave-myself-to-him/" class="wpml-ls-link">
        <img class="wpml-ls-flag" src=".../flags/en.png" alt="" width=18 height=12 />
        <span class="wpml-ls-native" lang="en">English</span>
      </a>
    </li>
    <li class="wpml-ls-slot-shortcode_actions wpml-ls-item wpml-ls-item-ayo wpml-ls-last-item wpml-ls-item-legacy-list-horizontal">
      <a href="https://ayore.org/ayo/culture/first-person-narratives/cotate-e-ye%cc%83ra-yu-to-ome-dupade/" class="wpml-ls-link">
        <img class="wpml-ls-flag" src=".../flags/ayo.jpg" alt="" width=18 height=12 />
        <span class="wpml-ls-native" lang="ayo">Ayoré</span>
      </a>
    </li>
  </ul>
</div>
```

### Key Observations
| Indicator | Meaning |
| :--- | :--- |
| `div.wpml-ls` | Container for the entire language switcher |
| `li.wpml-ls-item-{lang}` | One language option (e.g. `wpml-ls-item-en`, `wpml-ls-item-ayo`) |
| `a.wpml-ls-link` | The link to that language version — contains the target URL |
| `span.wpml-ls-native[lang="en"]` | The `lang` attribute identifies which language |

> [!IMPORTANT]
> The switcher shows only the **other** languages, not the current page's language. If you are on the ES page, the switcher lists EN and AYO — not ES.

### Python: Extract Language URLs from WPML Switcher
```python
def extract_language_urls(soup) -> dict[str, str]:
    """Extract URLs for all language versions from the WPML switcher.

    Call this on any already-scraped page to get the exact sibling URLs.
    The returned dict keys are language codes ('en', 'ayo', 'es', etc.).
    The current page's language is NOT included (WPML only shows others).
    """
    urls = {}
    switcher = soup.find("div", class_="wpml-ls")
    if not switcher:
        return urls
    for li in switcher.find_all("li", class_="wpml-ls-item"):
        span = li.find("span", class_="wpml-ls-native")
        a = li.find("a", class_="wpml-ls-link")
        if span and a:
            lang = span.get("lang")   # e.g. "en", "ayo"
            href = a.get("href")
            if lang and href:
                urls[lang] = href
    return urls
```

### Recommended Crawl Strategy
1. **Crawl the ES index** to get all Spanish story URLs (ES is always the most complete)
2. **For each ES story page**, fetch the page and call `extract_language_urls()` to get the exact EN and AYO URLs
3. **Store all three** under a shared `story_id` (use the ES slug as canonical key)

This is more reliable than crawling three index pages and pairing by position.

### ayore.org Site Structure

`ayore.org` is a WordPress site serving trilingual content (Spanish, English, Ayoré).

#### Content Sections
| ES path | EN/AYO path | Type |
| :--- | :--- | :--- |
| `cultura/creencias` | `culture/beliefs` | belief |
| `cultura/relatos-personales` | `culture/first-person-narratives` | personal_narrative |
| `cultura/comidas` | `culture/foods` | food |
| `cultura/juegos` | `culture/games` | game |
| `cultura/medicina` | `culture/medicine` | medicine |
| `cultura/canciones-nativas` | `culture/native-songs` | song |
| `cultura/historia-oral` | `culture/oral-history` | oral_history |
| `cultura/tradiciones-orales` | `culture/oral-traditions` | oral_tradition |
| `cultura/ensenanzas` | `culture/teachings` | teaching |

#### WordPress Content DOM
| Element | Selector | Notes |
| :--- | :--- | :--- |
| Main content | `div.entry-content` | Primary WordPress content div |
| Fallback | `article`, `div.post-content`, `main` | Try in order |
| Page title | `h1` | First `<h1>` on page |
| Body text | `p`, `blockquote` within content div | Skip fragments < 10 chars. Always invoke a helper to convert `<b>` and `<i>` to `**` and `*` Markdown natively before extracting text. |
| Glossary terms | `strong`/`b` + sibling text with `–` or `-` | Ayoreo term → Spanish definition |
| Body Decomposition | `scripts/add_body_decomposition.py` | Executed post-scrape. Iterates through the raw bodies and splits structures by checking for `**...` and `***...` (bold and bold-italic) headers at the start of `\n\n` paragraphs, while safely consuming trailing punctuation. |

#### Metadata Patterns (regex)
```python
# Narrator
r"(?:Narr?ador|Narrator|Narrated by)[:\s]+(.+?)(?:\n|$)"

# Location + year
r"(?:Campo Loro|Tobité|Zapocó|Santa Cruz|Poza Verde|Rincón del Tigre)[,\s]+(?:Bolivia|Paraguay)[,\s]*(\d{4})?"

# Transcriber / translator
r"(?:Transcri(?:bed|to) (?:by|por))[:\s]+(.+?)(?:\n|$)"
r"(?:Translat(?:ed|ado) (?:to Spanish )?(?:by|por))[:\s]+(.+?)(?:\n|$)"
```

#### Output Schema per Story
```json
{
    "story_id": "relatos-personales__cotade-me-he-entregado-dupade",
    "url_es":  "https://ayore.org/es/cultura/relatos-personales/cotade-me-he-entregado-dupade/",
    "url_en":  "https://ayore.org/culture/first-person-narratives/cotade-i-gave-myself-to-him/",
    "url_ayo": "https://ayore.org/ayo/culture/first-person-narratives/cotate-e-ye%cc%83ra-yu-to-ome-dupade/",
    "section": "relatos-personales",
    "type": "personal_narrative",
    "title_es": "...", "title_en": "...", "title_ayo": "...",
    "body_es":  "...", "body_en":  "...", "body_ayo":  "...",
    "body_decomposition": {
      "es": [{"header": null, "text": "..."}],
      "en": [{"header": null, "text": "..."}],
      "ayo": [{"header": null, "text": "..."}]
    },
    "glossary": [{"ayoreo": "Dupade", "spanish": "Dios"}],
    "metadata": {
        "narrator": "Cotade",
        "location": "Campo Loro, Paraguay",
        "year": "1985",
        "transcriber": "Maxine Morarie"
    },
    "scraped_at": "2026-03-01T..."
}
```

### Production Run Log
| Date | Section | Stories scraped | WPML corrections | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 2026-03-01 | `relatos-personales` | 14 | 13/14 (93%) | Positional pairing wrong for almost every story |

---

## Verification Checklist

### MCMP Scraper
- [x] All 54+ events captured via JSON API (no Selenium required)
- [x] Abstracts extracted from individual pages
- [x] No duplicate URLs
- [x] Dates in ISO format
- [x] Multi-day events have `date_end` from API
- [x] UTF-8 encoding enforced (no mojibake in smart quotes/accented characters)
- [x] Past events/people preserved across scraper runs (incremental merge)
- [x] News items scraped from JSON API (bypasses JS-rendered newsboard)
- [x] News stored separately in `data/news.json` with incremental merge

### ayore.org Scraper
- [ ] All three language versions discovered for each story
- [ ] Language URLs sourced from WPML switcher (not positional pairing)
- [ ] Anchor fragment URLs (`#`) filtered out in the crawler
- [ ] UTF-8 encoding enforced — no mojibake in Ayoreo/Spanish text
- [ ] `story_id` present and consistent across all three language versions
- [ ] Glossary extracted from ES pages
- [ ] Metadata (narrator, location, year) extracted where present
- [ ] No duplicate URLs within a section
- [ ] Empty/boilerplate pages flagged with a warning log
- [ ] All stories saved to a single `ayoreoorg.json` (not individual files)
- [ ] Incremental merge: re-running a section updates only that section's entries
