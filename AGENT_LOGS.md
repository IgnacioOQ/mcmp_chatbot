# AI Agent Logs

## [2026-03-06] Refactor Calendar UI out of HTML DOM

**Agent**: Antigravity
**Task**: Refactor the calendar DOM in app.py to follow native Streamlit widget semantics.

### Summary
The previous "Native Hybrid" implementation attempting to use pseudo-selectors alongside native stream buttons was still structurally fragile based on Streamlit's DOM handling wrapper rules. To ensure robust reliability, the system was fully transitioned away from html wrappers. Calendar rendering now relies strictly on pure loops and standard button mappings (primary/secondary/tertiary). Events are cleanly denoted using natively supported unicode string interpolation (the 🔵 emoji), removing the need for complex, bug-prone CSS overlays while retaining a tight layout via standardized test-id padding resets.

This file tracks major actions, architectural changes, and features implemented by AI agents functioning on this codebase.

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
