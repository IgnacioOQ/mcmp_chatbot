# AI Agent Logs

## [2026-03-20] Data Accumulation Fix & Dataset Recovery

**Agent**: Claude (Sonnet 4.6)
**Task**: Recover data removed by static scraper, fix the scraper to never remove entries, and update documentation.

### Root Cause
`MCMPScraper.save_to_json` was overwriting JSON files with only the freshly scraped data. Since the events overview page requires Selenium to click "Load more" (4+ times to reveal 53+ events) and Selenium was not available, the static scrape captured only 3 events. The overwrite reduced `raw_events.json` from 55 events to 3, and `people.json` lost 2 entries.

### Fix

1. **Data recovered**: Fetched `data/raw_events.json` and `data/people.json` from the GitHub remote (`origin/main`) and merged them with today's scrape — resulting in 55 events and 84 people (net +1 new person from this run).

2. **`MCMPScraper._accumulate()` added** (`src/scrapers/mcmp_scraper.py`): New helper that loads the existing file from disk, builds a map by unique key (`url` or `id`), updates matching entries with freshly scraped data, adds new entries, and leaves unmatched existing entries untouched. Returns the merged list.

3. **`MCMPScraper.save_to_json()` updated**: Now calls `_accumulate()` for all four datasets (`events`, `people`, `research`, `general`) before logging and writing to disk. The `_log_changes()` call was moved after accumulation so the log reflects the true diff against prior state (removed count will always be 0).

### Documentation Updated
- `docs/SCRAPER_AGENT.md`: Added "Data Accumulation Policy" section with caution callout, rationale, and step-by-step description of the merge logic.
- `README.md`: Updated "Data Maintenance" section to state entries are never removed, with a note clarifying the meaning of `"removed"` in `scraping_logs.json`.
- `docs/HTML_SCRAPING_SKILL.md`: Added explicit "never remove" caution callout to the "Single Output File + Incremental Merge" pattern.

### Changes
- `src/scrapers/mcmp_scraper.py`: Added `_accumulate()`, refactored `save_to_json()`.
- `data/raw_events.json`: Restored to 55 events.
- `data/people.json`: Restored to 84 people.
- `docs/SCRAPER_AGENT.md`, `README.md`, `docs/HTML_SCRAPING_SKILL.md`: Documentation updated.

---

## [2026-03-10] People Search Regression Fix

**Agent**: Antigravity
**Task**: Fix chatbot returning "cannot find [person]" despite person being in `data/people.json`.

### Root Cause (3 issues)
1. **`generate_response` missing `chat_history`**: The MCP-only refactor dropped the parameter; Gemini received each message as a fresh single-turn session.
2. **`app.py` not passing history**: `st.session_state.messages` was never wired into the engine call.
3. **`search_people` substring fragility**: `query in name` failed for reversed or partial names (though for "christian list" it technically matched — the problem was reproducible via conversation context loss).

### Fix
- Restored `chat_history: list = None` in `RAGEngine.generate_response` (`engine.py`) with full Gemini history conversion.
- Updated both `generate_response` call sites in `app.py` to pass `st.session_state.messages[:-1]`.
- Changed `search_people` in `tools.py` to use **word-token AND matching** on names (all tokens must appear anywhere in name), with full-substring fallback on descriptions.

### Verification
- `search_people('christian list')` → returns 8 results including `Prof. Dr. Christian List`.
- End-to-end `generate_response('who is christian list?', use_mcp_tools=True)` → full correct profile.

---

## [2026-03-10] Engine Latency Optimization

**Agent**: Antigravity
**Task**: Identify and fix latency bottlenecks in `src/core/engine.py`.

### Summary
Profiled the full query pipeline using `scripts/profile_latency.py`. Identified three major bottlenecks and applied all fixes, achieving a **~55% reduction in per-query latency** (8,100ms → 3,700ms avg):

1. **Removed `decompose_query` + `retrieve_with_decomposition`**: These methods made a separate Gemini API call (3–4s) to generate sub-queries for RAG vector search, which is no longer used. Removing them eliminated a full wasted LLM round-trip on every request.
2. **Removed `VectorStore` (ChromaDB) from `__init__`**: The vector store was still instantiated on startup even though RAG is not used, costing ~310ms per engine creation.
3. **Cached `genai.Client` at startup**: The Gemini client was recreated inside `generate_response()` on every call. Moving it to `__init__` (along with the personality text, tool list, and tool description string) makes per-call overhead negligible (< 1ms).

### Benchmark (before → after)
| Metric | Before | After |
|---|---|---|
| Full pipeline avg | 8,100 ms | 3,700 ms |
| Gemini client (per call) | 20 ms | 0 ms (cached) |
| `decompose_query` LLM call | ~3,500 ms | 0 ms (removed) |
| Engine init (MCP on) | 312 ms | 2,168 ms* |

*Engine init is now higher because it pre-warms the Gemini client — a one-time startup cost that saves ~20ms on every subsequent call.

### Changes
- Rewrote `src/core/engine.py` in full.
- Added `scripts/profile_latency.py` (new profiling tool).

---

## [2026-03-10] README Architecture Update

**Agent**: Antigravity
**Task**: Update `README.md` to accurately reflect the MCP + web scraping architecture.

### Summary
Rewrote `README.md` to remove all references to RAG, ChromaDB, vector databases, embeddings, and query decomposition, as the project no longer uses those components. The README now accurately describes the two-layer architecture: (1) **Web Scraping** via `scripts/update_dataset.py` to keep JSON data files fresh, and (2) **MCP Structured Tools** (`search_people`, `search_research`, `get_events`, `search_graph`) that the LLM calls to answer structured queries. Updated the Mermaid diagram, Features list, Technical Architecture sections, project structure tree, and all in-line prose to reflect this.

### Changes
- Rewrote `README.md` in full (removed ~80 lines of RAG/embedding content, rewrote all architecture sections).

---

## [2026-03-09] Parallel HTML Scraper Implementation

**Agent**: Antigravity
**Task**: Develop an HTML-only scraper and integrate it into the data pipeline.

### Summary
Created a parallel scraper (`html_mcmp_scraper.py`) that strictly uses HTML requests without Selenium, extracting data across events, people, research, and general information. Modified `scripts/update_dataset.py` to run both the primary `MCMPScraper` and the `HTMLMCMPScraper` concurrently, merge their results, deduplicate by unique identifiers (`url` or `id`), and output the combined data. Changes are automatically logged to `data/scraping_logs.json` during the `save_to_json()` step.

## [2026-03-06] Refactor Calendar UI out of HTML DOM

**Agent**: Antigravity
**Task**: Refactor the calendar DOM in app.py to follow native Streamlit widget semantics.

### Summary
The previous "Native Hybrid" implementation attempting to use pseudo-selectors alongside native stream buttons was still structurally fragile based on Streamlit's DOM handling wrapper rules. To ensure robust reliability, the system was fully transitioned away from html wrappers. Calendar rendering now relies strictly on pure loops and standard button mappings (primary/secondary/tertiary). Events are cleanly denoted using natively supported unicode string interpolation (the 🔵 emoji), removing the need for complex, bug-prone CSS overlays while retaining a tight layout via standardized test-id padding resets.

This file tracks major actions, architectural changes, and features implemented by AI agents functioning on this codebase.

## [2026-03-09] Fix Event Querying Bug
**Agent**: Antigravity
**Task**: Fix the event querying bug and broken tests.

### Summary
Fixed an issue where the chatbot was failing to retrieve events for specific dates (like April 07, 2026). The root cause was that `maximum_remote_calls` inside the `AutomaticFunctionCallingConfig` for the Gemini SDK was set to `1`. This allowed the SDK to fetch events using the tool but stopped it from making the subsequent API call needed to generate the final text answer. Increasing the limit to `3` resolved the issue.
Additionally, fixed a broken test in `tests/test_mcp.py` that was calling `search_people` with a removed keyword argument `role_filter`.

### Changes
- Updated `engine.py` to change `maximum_remote_calls=1` to `maximum_remote_calls=3` in `RAGEngine.generate_response`.
- Removed the `role_filter` argument from `search_people` in `tests/test_mcp.py`.

## [2026-03-05] Refactor Calendar UI to Native Hybrid

**Agent**: Antigravity
**Task**: Prevent browser hard-reloads while keeping the raw HTML/CSS calendar design.

### Summary
The user noted that previous attempts to fix the UI were incorrect and caused the Streamlit layout grid to "tilt". Reverted the CSS approach completely. The final working solution abandons injected HTML wrappers (which broke Streamlit 1.53's flexbox alignment) and instead uses **Pure Native Streamlit Buttons**. By mapping Streamlit's built-in button types (`type="primary"`, `"secondary"`, and `"tertiary"`) to specific days (Today, Event/Normal, and Empty Padding), we can cleanly target them with advanced CSS (`button[data-testid="baseButton-primary"]`) to perfectly recreate the original raw HTML gradient aesthetics without breaking the native grid alignment.

**Agent**: Antigravity
**Task**: Revert the calendar logic from native Streamlit buttons back to pure HTML/CSS.

### Summary
Restored the previous raw HTML and CSS implementation of the calendar component `app.py` due to user request, abandoning the native Streamlit button grid that was introduced in commit `b1a18d3`.

### Changes
- Replaced the Streamlit column-based calendar rendering in `app.py` with the former `calendar-grid` custom HTML logic.
- Restored URL query parameters (`?event_day=YYYY-MM-DD`) for clicking calendar events instead of Streamlit session state.

## [2026-03-05] Fix Unicode Misencodings in Scraper

**Agent**: Antigravity
**Task**: Standardize German umlauts and fix UTF-8 misencodings during scraping.

### Summary
Modified `src/scrapers/mcmp_scraper.py` inside the `_clean_text` function to properly map and convert misencoded UTF-8 string sequences (e.g. `Ã¼` to `ue`) into their valid representations, ensuring proper parsing of German names and typography.

### Changes
- Implemented a broad string replacement map in `_clean_text` prior to processing text lines.

## [2026-03-05] Implement Scraping Logs

**Agent**: Antigravity
**Task**: Create a mechanism to log additions, removals and updates after each scrape.

### Summary
Modified `src/scrapers/mcmp_scraper.py` to compare old and new dataset versions during the `save_to_json` process. Differences (added, removed, updated) for `events`, `people`, `research`, and `general` items are now appended to a running log in `data/scraping_logs.json`.

### Changes
- Implemented `_log_changes(self)` in `MCMPScraper`.
- Updated dataset saving pipeline to hook into this new method.

## [2026-03-05] Dataset Update via Scraping

**Agent**: Antigravity
**Task**: Run the data maintenance protocol to scrape and update datasets.

### Summary
Executed `scripts/update_dataset.py` to scrape the MCMP website and update the localized JSON datasets and institutional graph representations. Saved 54 events, 83 people, 4 research items, and 7 general items.

### Changes
- Updated `data/*.json` and `data/graph/` files to contain the latest scraped information from the MCMP website.

## [2026-01-28] Research Data Enhancement

**Agent**: Antigravity
**Task**: Enhance research data with hierarchical structure and link people to topics.

### Summary
Modified the scraper to organize research into hierarchical categories (Logic, Philosophy of Science, etc.) and implemented a topic matching utility to automatically link people to these research areas based on their profiles.

### Changes
-   **Scraper** (`src/scrapers/mcmp_scraper.py`): Implemented hierarchical categorization of research projects.
-   **Topic Matcher** (`src/utils/topic_matcher.py`): New utility to match text against research topics.
-   **Enrichment** (`scripts/enrich_metadata.py`): Integrated topic matching to populate `research_topics` in `people.json` and linked people to topics in `research.json`.

### Verification
-   Verified `research.json` contains structured categories.
-   Verified `people.json` contains `research_topics` metadata.

## [2026-01-28] Metadata Integration for Hybrid Search

**Agent**: Antigravity
**Task**: Implement metadata incorporation for hybrid RAG search.

### Summary
Integrated a metadata extraction and filtering system to allow the RAG engine to perform structured queries (e.g., "events in 2026", "postdocs in Logic Chair") alongside semantic search.

### Changes
1.  **Metadata Extractor** (`src/utils/metadata_extractor.py`):
    -   Created utility to parse unstructured text descriptions.
    -   Extracts: Dates, Times, Locations, Speakers (Events); Roles, Affiliations (People); Funding, Leaders (Research).

2.  **Enrichment Pipeline** (`scripts/enrich_metadata.py`):
    -   New script that processes existing `data/*.json` files.
    -   Injects extracted fields into a `metadata` dictionary for each item.

3.  **Vector Store Update** (`src/core/vector_store.py`):
    -   Updated `add_events` to index the new metadata fields in ChromaDB.
    -   Updated `query` method to support `where` clauses for filtering.

### Verification
-   Created `tests/verify_metadata.py` to validate filtering.
-   Confirmed that queries can be filtered by `meta_year`, `meta_role`, etc.

## [2026-01-28] Vector Search Optimization

**Agent**: Jules
**Task**: Optimize vector retrieval latency.

### Summary
Optimized `src/core/engine.py` and `src/core/vector_store.py` to use batch querying for vector retrieval, achieving ~82% reduction in latency (Benchmark: ~21.5s -> ~3.7s for 50 queries).

### Changes
-   Refactored `VectorStore.query` to accept a list of strings.
-   Refactored `RAGEngine.retrieve_with_decomposition` to send batched queries.
-   **Files Modified**: `src/core/engine.py`, `src/core/vector_store.py`, `tests/test_vector_store.py`.

## [2026-01-28] Repository Synchronization & Test Fix

**Agent**: Jules
**Task**: Synchronize repo and fix tests.

### Summary
Synchronized local repository with remote, installed dependencies, populated test data, and fixed a failing test in `tests/test_graph_manual.py`.

## [2026-01-28] Housekeeping & Diagnostics

**Agent**: Antigravity/Jules
**Task**: Verify system state.

### Summary
Executed multiple runs of the Housekeeping Protocol. Verified scraper functionality, fixed `chromadb` dependency issues, and updated `HOUSEKEEPING.md`.

## [2026-01-22] Remove Metadata Tool

**Agent**: Antigravity
**Task**: Create tool to remove metadata.

### Summary
Created `remove_meta.py` to reverse `migrate.py` effects and clean incomplete content.

### Changes
-   Created `language/remove_meta.py` with strict metadata detection logic.
-   Added flags `--remove-incomplete-content` and `--remove-incomplete-sections`.

## [2026-01-22] CLI Improvements

**Agent**: Antigravity
**Task**: Standardize Python CLIs.

### Summary
Improved Python CLIs in `manager` and `language` to be POSIX-friendly and support flexible I/O modes.

## [2026-01-22] Shell Wrapper for Python Scripts

**Agent**: Antigravity
**Task**: Create shell wrappers.

### Summary
Created a generic shell wrapper `sh2py3.sh` and symlinks for python scripts in `bin/` directory.
