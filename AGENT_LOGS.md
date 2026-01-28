# AI Agent Logs

This file tracks major actions, architectural changes, and features implemented by AI agents functioning on this codebase.

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
