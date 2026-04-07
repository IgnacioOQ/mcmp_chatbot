# AI Agent Logs
- status: active
- type: log
- description: Append-only history of agent interventions, architectural changes, and feature implementations.
- injection: informational

<!-- content -->

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

## [2026-04-07] Academic Offerings Scraper — Resolved ✅

**Status**: RESOLVED — feature is fully implemented and working in production.
**Agent**: Claude (Sonnet 4.6)
**Task**: Add scraping and MCP tool coverage for the MCMP "For Students" section (degree programs, application requirements, PhD pathways, learning materials).

---

### What Was Built

**New scraper method** (`src/scrapers/mcmp_scraper.py`):
- `scrape_academic_offerings()` — scrapes `mcmp/en/for-students/`, splits by `<h2>` into 4 sections (`bachelor`, `master`, `phd`, `learning_materials`), follows Bachelor and Master sub-pages for structured metadata (ECTS, deadlines, coordinators, required documents, contact emails).
- `_scrape_bachelor_details()` and `_scrape_master_details()` helpers.
- Class-level constants: `FOR_STUDENTS_URL`, `BACHELOR_URL`, `MASTER_URL`.
- `self.academic_offerings = []` added to `__init__`.
- `save_to_json()` and `_log_changes()` extended to handle `data/academic_offerings.json`.

**Time-gated scraping** (`scripts/update_dataset.py`):
- Academic offerings are throttled to at most once per 30 days (programs change infrequently).
- `--scrape-offerings` flag forces a re-scrape regardless.
- `should_scrape_academic_offerings()` checks `scraping_logs.json` for the last run timestamp.

**New MCP tool** (`src/mcp/tools.py`, `src/mcp/server.py`):
- `search_academic_offerings(query, offering_type)` — filters by type and keyword, returns structured program info (deadline, coordinators, contact, required docs, ECTS, duration, language).
- Registered in `MCPServer` and `list_tools()` with full JSON schema.
- Added `academic_offerings` to `_GREP_DB_MAP` so `grep_data` also searches it as a fallback.

**Load cache fix** (`src/mcp/tools.py`):
- Replaced `@functools.lru_cache` with a manual `_data_cache` dict. The old `lru_cache` permanently cached `[]` for any file that didn't exist at first call — meaning if a new dataset file was added after app startup, the tool would return empty forever until the process was restarted. The new dict only stores successful loads; missing files are never cached and retry on every call.

**Tool selection guide updated** (`src/core/engine.py`):
- Added explicit rule: "User asks about a degree program, MA, Master, Bachelor, PhD, how to apply → `search_academic_offerings(offering_type='...')`".
- Bumped `maximum_remote_calls` from 5 to 10.

**Personality updated** (`prompts/personality.md`):
- Added mandatory block format for academic offerings (mirrors the existing people/events formats), ensuring the LLM always includes a `Link:` bullet with the program URL.

---

### The Problem (Unresolved)

The chatbot consistently fails to answer questions about the MA program:

```
User: talk to me about the MA program

⚙️ Calling search_academic_offerings: master
⚙️ Calling search_academic_offerings: MA
⚙️ Calling search_academic_offerings: application
⚙️ Calling search_academic_offerings: master's program
🔎 Running text search: master

I am sorry, I cannot find any information about a Master's program at the MCMP.
```

The tool is called correctly by Gemini (4 times with different keyword extractions), but returns `[]` every time. The `grep_data` fallback finds only incidental mentions of "master" in `people.json` bios, not the actual program entry.

**Root cause confirmed via debug logging** (`journalctl --user -u streamlit-app`):

```
[search_academic_offerings] query=None offering_type='master' offerings_loaded=0
[search_academic_offerings] query='MA' offering_type=None offerings_loaded=0
[search_academic_offerings] query='application' offering_type='master' offerings_loaded=0
```

`offerings_loaded=0` on every call — `load_data("academic_offerings.json")` returns `[]` because **`data/academic_offerings.json` does not exist on the production server** (host `mcmp`, running via systemd service `streamlit-app`).

The file was generated locally (macOS, `/Users/ignacio/Documents/VS Code/GitHub Repositories/mcmp_chatbot/data/academic_offerings.json`, 5 entries, 8 KB) but was never transferred to the server or generated there.

**What we do NOT yet know**: the exact filesystem path where the server expects the file. A second diagnostic log line was added:

```python
_log(f"... path_exists={_os.path.exists(_expected_path)} path={_expected_path}")
```

This log line was added but the `path=` value has not been captured yet because the app was not restarted after this log was added (or the log output was not collected). This log is still present in `tools.py` and will emit on next restart + query.

**What was ruled out during debugging**:
- The tool function itself works correctly — verified by direct `python3 -c` invocation, returning 1 result for `offering_type='master'`.
- The instrumented wrapper (used by Gemini's automatic function calling) also works correctly — verified via `MCPServer.get_instrumented_tools()` test.
- File permissions are fine (`-rw-r--r--`).
- `DATA_DIR` is computed correctly from `__file__` (absolute path, not CWD-dependent).
- The `_data_cache` replacement correctly handles missing files without caching the empty result.
- The issue is purely that the file is absent from the server's filesystem.

---

### Resolution

- **Root cause confirmed**: `data/academic_offerings.json` was gitignored (the entire `data/` directory is excluded) so it was never deployed to the server (`/home/ignacio/mcmp_chatbot/data/academic_offerings.json`). The debug log confirmed `path_exists=False` on every tool call.
- **Fix**: Added `!data/academic_offerings.json` to `.gitignore` (alongside the existing `!data/scraping_logs.json` exception) and committed the file to the repository. The server pulls it via `git pull` like all other code changes.
- **Verified**: Chatbot now returns the full MA program block with link when asked "talk to me about the MA program".
- **Cleanup pending**: Remove the two temporary debug log lines from `search_academic_offerings` in `src/mcp/tools.py`.

---

### All Code Changes Made (All on Local, Deployed to Server via Git Except the JSON Data File)
- `src/scrapers/mcmp_scraper.py`: Added constants, `self.academic_offerings`, `scrape_academic_offerings()`, `_scrape_bachelor_details()`, `_scrape_master_details()`, extended `save_to_json()` and `_log_changes()`.
- `scripts/update_dataset.py`: Added `argparse`, `should_scrape_academic_offerings()`, `--scrape-offerings` flag.
- `src/mcp/tools.py`: Added `search_academic_offerings()`, added `academic_offerings` to `_GREP_DB_MAP`, replaced `lru_cache` with `_data_cache` dict, added **temporary debug log** (still present — remove after resolution).
- `src/mcp/server.py`: Imported and registered `search_academic_offerings` in tools dict and `list_tools()`.
- `src/core/engine.py`: Updated tool selection guide, bumped `maximum_remote_calls` to 10.
- `prompts/personality.md`: Added academic offering block format.
- `data/academic_offerings.json`: **Created locally only. 5 entries: bachelor, master, phd, learning_materials, learning_materials list. NOT on server.**

---

## [2026-04-01] Caching in MCP Tools

**Agent**: Jules
**Task**: Implement caching for `load_data` in MCP tools to improve execution speed.

### Summary
Added `@functools.lru_cache` to `load_data` in `src/mcp/tools.py` to prevent repeated disk I/O when reading JSON files across tool calls during the same session, reducing execution latency. Also removed stale tests from `tests/test_engine.py` referencing removed code (`VectorStore`, `retrieve_with_decomposition`, `decompose_query`).

---

## [2026-04-01] grep_data MCP Tool + Live Tool Status Display

**Agent**: Antigravity
**Task**: Add a flexible grep/regex search tool to the MCP layer, and display active tool calls in the Streamlit UI in real time.

### grep_data Tool
Added `grep_data()` to `src/mcp/tools.py` — a flexible text search across MCMP databases (people, research, events). Unlike the specialized tools, it scans the full text of every record using a plain substring or regex pattern and returns compact `>>>match<<<`-annotated snippets showing exactly where the hit occurred.

Supporting helpers added to the same file:
- `_flatten(obj)` — recursively yields `(dotted.key.path, str_value)` pairs from any JSON object, making nested fields like `metadata.selected_publications[2]` fully searchable.
- `_match_span(pattern, text, use_regex)` — returns the `(start, end)` of the first match; falls back to substring if an invalid regex is provided.
- `_snippet(text, span)` — cuts an 80-character window around the match.

Registered in `src/mcp/server.py` with a full JSON Schema so all providers see it correctly.

### Live Tool-Call Status Display
**Core idea**: Pass an optional `status_callback` from `app.py` → `engine.generate_response()` → `MCPServer.call_tool()`. When fired, it updates a Streamlit `st.status()` widget so users see which tool is running and with what argument in real time. For Gemini (which uses `automatic_function_calling` and calls raw Python functions directly), the tool functions themselves are wrapped via the new `MCPServer.get_instrumented_tools()` method so the callback fires before each execution.

### Changes
- `src/mcp/tools.py`: Added `grep_data()`, `_flatten()`, `_match_span()`, `_snippet()`, `_GREP_DB_MAP`.
- `src/mcp/server.py`: Registered `grep_data`; added `status_callback` param to `call_tool()`; added `get_instrumented_tools()`.
- `src/core/engine.py`: Added `status_callback` param to `generate_response()`; routes it to both Gemini (via `get_instrumented_tools`) and OpenAI (via `call_tool`) paths.
- `app.py`: Replaced both `st.spinner()` blocks with `st.status()` + a `_callback` closure that writes a tool-icon line on each invocation.

