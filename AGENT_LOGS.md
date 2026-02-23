# AI Agent Logs

This file tracks major actions, architectural changes, and features implemented by AI agents functioning on this codebase.

## Dataset Size History
### [2026-02-23] (Scrape 2)
- raw_events.json: ~152 KB (54 entries, +0 new)
- people.json: ~235 KB (83 entries, +0 new)
- research.json: ~12 KB (4 entries, +0 new)
- general.json: ~6 KB (6 entries, +0 new)
- news.json: ~19 KB (9 entries, +0 new)

### [2026-02-23]
- raw_events.json: ~152 KB (54 entries)
- people.json: ~235 KB (83 entries)
- research.json: ~12 KB (4 entries)
- general.json: ~6 KB (6 entries)
- news.json: ~19 KB (9 entries)

## [2026-02-23] Execute Scraping Protocol

**Agent**: Antigravity
**Task**: Run the dataset update script to fetch latest events and people.

### Summary
Executed `python scripts/update_dataset.py` as requested by the user, successfully updating the datasets and confirming accumulation of data. Included file size tracking as mandated by the `SCRAPER_AGENT.md` guidelines.

## [2026-02-23] Accumulate JSON Data Scrapes

**Agent**: Antigravity
**Task**: Enable data accumulation for research and general scraped data.

### Summary
Modified the `save_to_json` method in `MCMPScraper` to correctly accumulate and merge `research.json` and `general.json` data rather than overwriting existing records.

### Changes
-   **Scraper** (`src/scrapers/mcmp_scraper.py`): Replaced list overwrite logic with dictionary-based iterative merges that retain old categories and projects for research, and uses existing `_merge_and_save` for general info.
-	**Script**: Executed `python scripts/update_dataset.py` to test the new logic, successfully merging the data and confirming accumulation.

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
