# MCMP Scraping Reference
- status: active
- type: reference
- description: MCMP-specific scraping specification — LMU JSON APIs for events and news, DOM selectors for individual event and people profile pages, output schemas, single-class `MCMPScraper` architecture, URL-keyed accumulation policy, the MCP field-name alignment anti-pattern (`chair` vs `organizational_unit`), 404/departed-people handling, and the `WORKLOG.md` dataset-size logging protocol.
- label: [backend, scraper, reference]
- injection: informational
- volatility: evolving
- scope: project-specific
- last_checked: 2026-05-12
<!-- content -->
This document is the project-specific reference for the MCMP scraper. It captures everything that is genuinely tied to the Munich Center for Mathematical Philosophy website and the MCMP Chatbot codebase — JSON API endpoints, DOM selectors, output schemas, the single-class scraper layout, the URL-keyed accumulation contract, the MCP field-alignment anti-pattern, departed-people handling, and the dataset-size logging protocol.

Generic web scraping patterns applicable across sites — UTF-8 encoding enforcement, anchor-fragment filtering, URL normalization, deduplication, section-content extraction, date parsing, WPML multi-language scraping, linked-list traversal, and Selenium "Load more" handling — live in the shared knowledge base (`content/how-to/WEB_SCRAPING_SKILL.md`). Reach for that doc for technique, and this one for "what does the MCMP site look like and what does our scraper write."

---

## Primary Data Sources

### Events — JSON API (primary)
- **Endpoint**: `https://www.philosophie.lmu.de/mcmp/site_tech/json-newsboard/json-events-newsboard-en.json`
- Discovered from the `jsonUrl` attribute of the `LmuNewsboard` Vue component on the events-overview page.
- Returns **all events** reliably (54+) without Selenium or dynamic page loading.

> [!NOTE]
> The events-overview page is JS-rendered via `LmuNewsboard.init()`. The JSON API bypasses this entirely, making Selenium optional.

**How it works:**
1. Fetch JSON index from the API — returns all events with `id`, `date`, `dateEnd`, `link.href`, `link.text`.
2. Pre-populate metadata from API data (`date`, `date_end` for multi-day events).
3. Scrape each individual event page for full details (speaker, abstract, location, times).
4. Selenium + static HTML scraping remain as supplements for events that the API might miss.

**API response schema:**
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

### Events — Selenium (legacy fallback)
The events-overview page uses a "Load more" button for dynamic loading. Selenium clicks it repeatedly to reveal all events. This is now only used as a supplement to the JSON API. Optional dependencies: `selenium`, `webdriver-manager`.

### Events — Static HTML (final fallback)
Static `requests`-based scraping of the events page and the homepage covers events linked outside the newsboard.

### News — JSON API
- **Endpoint**: `https://www.philosophie.lmu.de/mcmp/site_tech/json-newsboard/json-news-newsboard-en.json`
- Discovered from the `data-` attributes of the `LmuNewsboard` Vue component on the news-overview page.

> [!NOTE]
> The news-overview page (`/latest-news/news-overview/`) is fully JS-rendered via `LmuNewsboard.init()`. Static scraping sees no content. The JSON API endpoint bypasses this entirely.

**How it works:**
1. Fetch the JSON index from the API — returns a list of news items with `id`, `date`, `link.href`, `link.text`.
2. Scrape each individual news page for full content (`div.rte__content` or fallback to `main`).
3. Store in `data/news.json` with incremental URL-keyed merge (same contract as events/people).

**API response schema:**
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

**Content types** typically found on the news feed: job postings (PhD, postdoc, faculty), calls for papers/abstracts, award announcements (Karl-Heinz Hoffmann Prize, Kurt Gödel Award), publication announcements, partnership announcements.

The news feed is exposed to the LLM via a dedicated `search_news(query)` MCP tool — kept separate from `get_events` because news and events are semantically different.

---

## Individual Event Page — DOM Structure

- `<h1>` with speaker/event name.
- `<h2>` labels for `Date:`, `Location:`, `Title:`, `Abstract:`. Use the generic section-extraction helper to walk siblings until the next header.
- Location appears in an `<address>` tag.

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

---

## Individual People Profile Page — DOM Structure

| Field | Selector / Logic | Notes |
| :--- | :--- | :--- |
| **Name** | `h1.header-person__name` | Fallback to `h1`. |
| **Position** | `p.header-person__job` | e.g. "Doctoral Fellow". |
| **Org Unit** | `p.header-person__department` | e.g. "Chair of Philosophy of Science". Written to `metadata.organizational_unit` — see field-alignment anti-pattern below. |
| **Email** | `a.header-person__contentlink.is-email` | Strip "Send an email"; fallback to `mailto:` href. |
| **Phone** | `a.header-person__contentlink.is-phone` | |
| **Room** | `div.header-person__detail_area p` | **CRITICAL**: match "Room" but **exclude** "Room finder". |
| **Office address** | Same area as room | Match "Ludwigstr" or "Geschwister-Scholl". |
| **Image** | `img.picture__image` | Get `src` attribute. |
| **Website** | `<a>` with text "Personal website" | |
| **Publications** | `h2` "Selected publications" | `find_parent("div", class_="rte__content")` → `ol` / `ul`. |

**Main content** for the person's bio: extract from `div.rte__content` divs inside `div#r-main`, skipping the publications section already captured above.

---

## Output Schemas

### Events (`data/raw_events.json`)
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

### People (`data/people.json`)
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

### News (`data/news.json`)
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

---

## Single-Class Scraper Architecture

The MCMP scraper lives entirely in **`src/scrapers/mcmp_scraper.py`** as a single `MCMPScraper` class. No inheritance, no parallel scrapers.

**Why a single class is sufficient**: `MCMPScraper.scrape_events()` already tries Selenium first (to handle the "Load more" button), then falls back to static `requests` scraping for all other `EVENT_SOURCES`. A separate static-only scraper (`HTMLMCMPScraper`) was redundant because Selenium's fallback path covers the same pages.

**Structure:**

```
MCMPScraper                         # src/scrapers/mcmp_scraper.py
├── __init__()                      # all state + _scraped_person_urls set
│
├── # Core helpers
├── _fetch_page()                   # UTF-8 + ftfy — never call requests.get() directly
├── _clean_text()
├── load_important_urls()
├── _normalize_url()
├── _is_event_link()
│
├── # Scraping methods
├── scrape_events()                 # Selenium for events-overview + static fallback
├── _fetch_events_with_selenium()
├── scrape_event_details()
├── _extract_section_content()
├── _parse_date_time()
├── scrape_people()                 # anchor-fragment filter included
├── _scrape_single_person_page()    # O(1) dedup via _scraped_person_urls set
├── scrape_research()
├── _scrape_single_research_page()
├── scrape_general()                # append OUTSIDE the while loop
├── scrape_reading_groups()
│
└── # Persistence
    ├── _accumulate()
    ├── _log_changes()
    └── save_to_json()
```

**Key design rules:**
- Module-level imports only — no `import x` inside function bodies.
- `_scraped_person_urls: set` is initialized in `__init__` for O(1) person deduplication.
- Constants (`BASE_URL`, `EVENT_SOURCES`, etc.) are class-level attributes.
- `scripts/update_dataset.py` calls this class directly — no merge logic needed at the call site.

---

## Incremental Scraping (Accumulation Policy)

The scraper preserves historical data across runs using `_merge_and_save()` / `_accumulate()`:
- **Events and People**: merged by URL key. Records from previous scrapes that no longer appear on the website are **retained**. Only matching URLs get updated.
- **Research and General**: **overwritten** each run — structural merge is too complex for hierarchical category data.
- **News**: merged by URL key, same contract as events and people.

> [!CAUTION]
> **Entries are NEVER removed from JSON datasets.** The scraper accumulates data over time. If an entry disappears from the source (e.g. "Load more" not triggered, page taken down), its record is preserved in the JSON file.

**Why**: a dynamic page may require Selenium to load all items. A static fallback run can capture only a fraction. Without accumulation, a static fallback would wipe out previously scraped entries.

The `_log_changes()` method still records `"removed"` entries for auditing (absent from this scrape) but they are **not** deleted from the file.

This ensures a growing knowledge base where past events remain queryable even after they leave the website.

---

## MCP Field-Name Alignment Anti-Pattern

> [!CAUTION]
> **Correct scraping is necessary but not sufficient.** A field can be scraped perfectly and stored in JSON, yet the LLM still reports "Unknown" — if the MCP tool reads a different field name than the one the scraper wrote.

**Production incident (2026-04-01):** the scraper stored `metadata.organizational_unit` for every person. The `search_people()` MCP tool read `metadata.chair` — a key that never existed. Result: the LLM reported `"Unknown"` for every person's chair, even though the data was correct in `people.json`.

The fix was a one-liner in `src/mcp/tools.py`:
```python
# Before (broken)
"chair": person.get("metadata", {}).get("chair", "Unknown"),
# After (correct)
"chair": person.get("metadata", {}).get("organizational_unit", "Unknown"),
```

**Root cause pattern**: the scraper and the MCP tool were written independently with no shared schema. When debugging LLM output, always check the full chain:

```
scraper writes                MCP tool reads               LLM sees
─────────────────             ─────────────────            ──────────────
metadata.organizational_unit  →  metadata.chair             →  "Unknown"  ✗
metadata.organizational_unit  →  metadata.organizational_unit  →  "Chair of X"  ✓
```

### Debugging checklist when the LLM returns wrong data
1. **Check the data file directly** — is the field present and correct?
2. **Run the MCP tool in isolation** — does it return the expected value?
3. **Check field name alignment** — does the key the MCP tool reads match what the scraper writes?
4. **Check the tool's output schema** — is the field included in the returned dict at all?

---

## 404 Pages and Departed People

Pages that return HTTP 404 (e.g. people who left the institution) are handled gracefully:
- `_fetch_page()` calls `raise_for_status()` → raises an exception.
- `_scrape_single_person_page()` catches it and logs the error → no new entry added.
- The accumulation policy (`_accumulate()`) **preserves the existing entry** from the last successful scrape.

This means data for departed people is kept in `people.json` rather than silently deleted — consistent with the never-remove policy.

---

## Dataset Size Tracking

> [!IMPORTANT]
> To monitor the growth of the knowledge base, agents must log the file sizes of the generated datasets into `WORKLOG.md` after running the scraper.

### Logging protocol
After successfully executing `scripts/update_dataset.py`:
1. Examine the file sizes of the primary datasets located in `data/`.
2. Inspect the JSON files to count the total number of top-level entries (e.g. number of events, number of people) in each. Compare to the previous run to note if new entries were added.
3. Open `WORKLOG.md` and locate (or create) the `## Dataset Size History` section.
4. Append a new entry with the current date, the sizes (in KB/MB), the exact entry counts, and a `(+X new)` note if applicable.

Example format for `WORKLOG.md`:
```markdown
### [YYYY-MM-DD]
- events.json: 85 KB (51 entries, +2 new)
- people.json: 210 KB (80 entries, +0 new)
- research.json: 45 KB (4 entries, +0 new)
- general.json: 12 KB (6 entries, +0 new)
- news.json: 30 KB (8 entries, +1 new)
```

---

## Verification Checklist (MCMP-specific)

- [ ] All 54+ events captured via the JSON API (no Selenium required for the primary path).
- [ ] Abstracts extracted from individual event pages.
- [ ] No duplicate URLs in `data/raw_events.json` or `data/people.json`.
- [ ] Dates stored in ISO 8601 (`YYYY-MM-DD`).
- [ ] Multi-day events carry `date_end` from the API.
- [ ] Past events and people preserved across scraper runs (URL-keyed incremental merge).
- [ ] News scraped via the JSON API (static scraping sees no content on the JS-rendered overview).
- [ ] News stored separately in `data/news.json` with the same incremental merge contract.
- [ ] `metadata.organizational_unit` written by the scraper aligns with the key read by `search_people()` in `src/mcp/tools.py`.
- [ ] 404s on departed-person pages are caught — the prior `people.json` entry remains intact.
- [ ] `WORKLOG.md` updated with new dataset sizes and entry counts after each `update_dataset.py` run.
