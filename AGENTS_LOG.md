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

### 2026-02-02: Housekeeping Execution (Antigravity)
- **Task**: Periodic Housekeeping Protocol Execution.
- **Changes**:
    - Updated dataset via `scripts/update_dataset.py`.
    - Validated all tests (`pytest`) and connection checks.
    - Updated `docs/HOUSEKEEPING.md` with status report.
- **Outcome**: System healthy with 53 scraping events. `test_search_people` failing in MCP (known issue).
