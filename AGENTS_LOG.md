# Agents Log
- status: active
- type: log
- context_dependencies: {"guideline": "AGENTS.md"}
<!-- content -->

## Intervention History
- status: active
<!-- content -->

### 2026-01-31: Housekeeping Execution (Antigravity)
- **Task**: Executed Housekeeping Protocol & Fixed Scraper.
- **Problem**: Scraper was falling back to static mode (3 events) due to missing dependencies.
- **Fix**: Installed `selenium`, `webdriver-manager` and updated `requirements.txt`.
- **Changes**: 
    - Verified `chromadb` installation.
    - Updated dataset via `scripts/update_dataset.py` (Now finds **53 events**).
    - Ran all unit tests and connectivity checks.
    - Updated `docs/HOUSEKEEPING.md` with corrected report.
- **Outcome**: System healthy. 53 events scraped. Minor regression in MCP tests noted.

### 2026-01-31: Fix Future Event Access (Antigravity)
- **Task**: Debugging LLM refusal to access future events.
- **Problem**: LLM refused to answer questions about future events (e.g., Feb 2026) despite data being in `raw_events.json`. Error message ("I can only access information from the provided context") indicated strictly following RAG-only context rules in personality.
- **Fix**: Modified `prompts/personality.md` to explicitly authorize and mandate Tool usage (`get_events`) when text context is insufficient.
- **Changes**:
    - Updated `prompts/personality.md` "Behavioral Guidelines" and "What to Avoid".
    - Verified `get_events` tool logic with `test_events.py` (Tool works correctly).
- **Outcome**: LLM personality now prioritize Tool usage over politeness when data is missing from text chunks.

### 2026-01-31: Model Default Switch (Antigravity)
- **Task**: Fix "Future Event Access" failure on default settings.
- **Problem**: `gemini-2.0-flash-lite` (previous default) consistently failed to use the `get_events` tool for speaker queries, hallucinating a capability limitation ("I cannot search for events by speaker").
- **Fix**: 
    - Switched default model in `app.py` from Lite (Index 1) to **Gemini 2.0 Flash** (Index 0).
    - Updated `src/mcp/server.py` tool schema to explicitly mention "speaker name" in the query description (as a best practice, though Lite still struggled).
- **Outcome**: Default system now uses the more capable Flash model, which correctly calls tools and answers future event queries.

### 2026-01-31: Enhance Calendar Prompt (Antigravity)
- **Task**: Improve detail in calendar-triggered event queries.
- **Change**: Updated the `auto_prompt` in `app.py` (triggered by calendar clicks) to explicitly request an "abstract or description".
- **Goal**: Ensure the LLM provides more content about the talk, not just the title/time.

### 2026-02-02: Re-implement MCP Awareness (Antigravity)
- **Task**: Re-inject MCP Protocol into System Prompt & Enhance Tool Descriptions.
- **Problem**: LLM was providing minimal info for events because it wasn't fully aware of `get_events` capabilities.
- **Fix**: Re-applied prompt dynamic injection in `src/core/engine.py` (fetching tools list) and updated `src/mcp/server.py` to explicitly state `get_events` returns matching titles/abstracts.
- **Outcome**: LLM now has explicit instructions to use `get_events` for detailed data. Unit tests passed.

### 2026-02-02: Force Tool Usage (Antigravity)
- **Task**: Forcing automatic tool usage without permission-asking.
- **Problem**: LLM was politely asking "Would you like me to check?" instead of checking automatically, violating the seamless RAG experience.
- **Fix**: 
    - Updated `src/core/engine.py` system prompt injection with "IMPORTANT: You have permission... Do NOT ask... Just check."
    - Updated `prompts/personality.md` to explicitly forbid asking for permission.
- **Outcome**: Prompt instructions are now imperative and strictly enforce automatic tool usage.

### 2026-02-02: Fix RAG vs MCP Conflict (Antigravity)
- **Task**: Resolving conflict where partial RAG context prevented tool usage.
- **Problem**: LLM was satisfied with just an event title from the vector store and didn't call tools to get the missing abstract/time.
- **Fix**: 
    - Updated `prompts/personality.md` to relax "Context-First" rule: *"If context is incomplete... YOU MUST use tools to enrich it."*
    - Updated `src/core/engine.py` prompt injection to explicitly handle partial info scenarios.
- **Outcome**: LLM should now recognize "Title-only" context as insufficient and trigger `get_events` for enrichment.

### 2026-02-02: Housekeeping Execution (Jules)
- **Task**: Executed Housekeeping Protocol & Fixed Data/MCP.
- **Problem**:
    - `update_dataset.py` failed due to missing `data/graph` directory.
    - `test_search_people` failed due to role/position mismatch in metadata.
- **Fix**:
    - Manually created `data/graph` and rebuilt graph.
    - Updated `src/mcp/tools.py` to check both "role" and "position" in metadata.
- **Changes**:
    - Installed missing python dependencies.
    - Updated dataset (53 events, 82 people).
    - Fixed `src/mcp/tools.py`.
    - Verified all tests pass.

### 2026-02-07: Housekeeping Re-run (Antigravity)
- **Task**: Re-run Housekeeping & Verify Fixes.
- **Problem**: Routine maintenance and verification of user-refined fixes.
- **Changes**: 
    - Re-ran `scripts/update_dataset.py` (53 events, 83 people).
    - Verified `src/mcp/tools.py` (User's fix for `role`/`position` fallback).
    - Ran full test suite (15/15 passed).

### 2026-02-07: Incremental Scraping Implementation (Antigravity)
- **Task**: Implement Data Persistence.
- **Problem**: User requested that past scraping data be preserved. Previous implementation overwrote data files.
- **Fix**: 
    - Implemented `_merge_and_save` method in `src/scrapers/mcmp_scraper.py`.
    - Merges new data with existing JSON records based on URL.
    - Added unit test `tests/test_scraper.py::test_merge_and_save` to verify logic.

### 2026-02-07: Housekeeping Post-Feature (Antigravity)
- **Task**: Re-run Housekeeping protocol after enabling Incremental Scraping.
- **Outcome**: 
    - Dataset updated with merge logic active.
    - All 16 tests passed (including new persistence test).
    - `README.md` and `HOUSEKEEPING.md` updated.
    - System is fully operational with historical data preservation.

### 2026-02-14: Remove RAG, Switch to MCP-Only Architecture (Antigravity)
- **Task**: Remove the RAG pipeline (ChromaDB, embeddings, query decomposition) and switch to an MCP-only architecture.
- **Rationale**: Datasets are small (~400 KB total). The RAG pipeline added latency (query decomposition LLM call + embedding + vector search) without proportional value. MCP tools provide direct, fast access to the same data.
- **Changes**:
    - **Deleted**: `src/core/vector_store.py`, `tests/test_vector_store.py`, `tests/verify_metadata.py`, `reproduce_truncation.py`.
    - **Rewritten**: `src/core/engine.py` — `RAGEngine` → `ChatEngine`. Removed `decompose_query`, `retrieve_with_decomposition`, `VectorStore` init. MCP tools always enabled.
    - **Added**: `search_graph()` tool in `src/mcp/tools.py` and registered it in `src/mcp/server.py`. Exposes institutional graph as an MCP tool.
    - **Updated**: `app.py` — removed auto-refresh VectorStore block, MCP toggle, RAG references.
    - **Updated**: `tests/test_engine.py` — rewritten for `ChatEngine`. `tests/test_mcp.py` — added `test_search_graph`.
    - **Updated**: `requirements.txt` — removed `chromadb` dependency.
    - **Updated**: `README.md` — replaced RAG architecture description with MCP-only architecture, updated Mermaid diagram and project structure.
- **Outcome**: All 12 tests pass. Architecture simplified from 3-phase pipeline to direct LLM + MCP tools.
