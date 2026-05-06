# Latency Monitoring & Optimization
- status: active
- type: reference
- description: Latency instrumentation, measured baselines, known bottlenecks, and the optimization playbook for the MCMP Chatbot pipeline.
- injection: informational
- last_updated: 2026-05-06

<!-- content -->

This document defines the latency instrumentation in the MCMP Chatbot pipeline, documents known bottlenecks, and provides guidelines for diagnosing and optimizing response times.

For the **transferable, repo-agnostic principles** (round-trip dominance, AFC bypass, server-side dedupe, streaming with `send_message_stream`, model selection for tool-calling workloads), see the knowledge-base document `content/how-to/GEMINI_CHATBOT_LATENCY_SKILL.md`. This file is the project-local companion: it tracks what is actually measured, deployed, and outstanding *in this repository*.

> [!NOTE]
> **Architecture note (updated 2026-03-10):** The pipeline no longer uses RAG / ChromaDB / vector search. All data access goes through **MCP structured tool calls** (`search_people`, `search_research`, `get_events`, `search_graph`, `search_academic_offerings`, `grep_data`) against local JSON files. The `decompose_query` pre-call has been removed.

---

## 1. Instrumentation Overview
The pipeline uses a `log_latency` context manager (`src/utils/logger.py`) that wraps each stage with `time.perf_counter()` and logs elapsed milliseconds as `[LATENCY] stage_name: X.Xms`.

### Instrumented Stages

| Stage | File | What It Measures |
|:---|:---|:---|
| `build_system_instruction` | `engine.py` | Formatting current date into the system prompt |
| `build_tools` | `engine.py` | Resolving provider-specific tool objects for this call |
| `gemini_chat_create` | `engine.py` | `client.chats.create()` with config (client itself is cached) |
| `llm_api_call` | `engine.py` | LLM network call — `chat.send_message()` incl. auto tool calls |
| `llm_api_call_2` | `engine.py` | Second LLM call after tool results (OpenAI only) |
| `tool:{name}` | `server.py` | Individual MCP tool execution (e.g., `tool:get_events`) |

> [!NOTE]
> `log_latency` is a **context manager**, not a decorator. Always use it with `with log_latency("stage_name"):`. Do NOT use it with `@log_latency(...)` as a decorator — `@contextmanager` functions are not decorators.

### How to Read the Logs

```bash
grep "\[LATENCY\]" mcmp_chatbot.log
```

Example output for a Gemini request with one tool call:
```
[LATENCY] build_system_instruction: 0.0ms
[LATENCY] build_tools: 0.1ms
[LATENCY] gemini_chat_create: 0.3ms
[LATENCY] llm_api_call: 3910.9ms    ← includes tool call + final synthesis
[LATENCY] tool:get_events: 4.9ms    ← logged separately by server.py
```

### The `log_latency` Context Manager

Defined in `src/utils/logger.py`:
```python
@contextmanager
def log_latency(stage: str):
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"[LATENCY] {stage}: {elapsed_ms:.1f}ms")
```

Use `time.perf_counter()` (not `time.time()`) for monotonic, high-resolution timing unaffected by system clock adjustments.

### Profiling Script

A dedicated profiler is available at `scripts/profile_latency.py`. It benchmarks each stage in isolation and writes `scripts/latency_report.json`:

```bash
python scripts/profile_latency.py
python scripts/profile_latency.py --query "Who is Hannes Leitgeb?" --runs 3
python scripts/profile_latency.py --skip-full   # skips Gemini API calls
```

---

## 2. Pipeline Anatomy
A single request flows through these stages in order:

```
User Query (app.py)
  |
  v
generate_response()  [or generate_response_stream() for the streaming path]
  |
  +-- _build_system_instruction()   [build_system_instruction]  ~0ms  (string format, no I/O)
  +-- resolve tool objects          [build_tools]               ~0ms  (in-memory)
  +-- create chat session           [gemini_chat_create]        ~0ms  (in-memory, client is pre-cached)
  +-- LLM API call                  [llm_api_call]              ~2-5s (network + inference)
  |     |
  |     +-- (Gemini auto-function-calling triggers tool calls internally, max 3 round-trips)
  |     +-- each tool logs individually via [tool:{name}]
  |
  +-- (OpenAI only) LLM API call #2 [llm_api_call_2]           ~0.5-1.5s
```

**What is pre-cached at `ChatEngine.__init__` (not per-call):**
- `self._gemini_client` — `genai.Client()` created once, reused for all calls
- `self._personality` — `prompts/personality.md` read once from disk
- `self._tool_defs` — MCP tool definition list (static)
- `self._tools_description_str` — formatted tool section for the system prompt (static)

### Provider Differences

| Provider | Tool Calling Model | Instrumentation Notes |
|:---|:---|:---|
| **Gemini** | `automatic_function_calling` (capped at 3 round-trips) | `llm_api_call` includes tool execution time since Gemini handles it internally. `tool:{name}` still logs individually. |
| **OpenAI** | Explicit two-call loop | `llm_api_call` = first call, `tool:{name}` = each tool, `llm_api_call_2` = second call with results. |
| **Anthropic** | No tool calling implemented yet | Only `llm_api_call` is logged. |

---

## 3. Measured Baselines
### Baseline A — Before Optimizations (2026-02-14)
Gemini 2.0 Flash, single query ("What is the next upcoming talk?"), RAG + decompose pipeline:

| Stage | Time | Notes |
|:---|---:|:---|
| `gemini_import` | 1939ms | Lazy import on first request |
| `decompose_query` (LLM call) | ~3500ms | Extra Gemini call to generate RAG sub-queries |
| `llm_api_call` | 2707ms | Main LLM call |
| `gemini_client_init` | 208ms | Per-request client creation |
| VectorStore init (ChromaDB) | 310ms | Startup cost |
| **total** | **~8100ms avg** | |

### Baseline B — After Optimizations (2026-03-10)
Gemini 2.0 Flash, same query, MCP-only pipeline:

| Stage | Time | Notes |
|:---|---:|:---|
| `build_system_instruction` | 0.0ms | Pre-cached, only date formatting |
| `build_tools` | 0.0ms | Pre-cached tool objects |
| `gemini_chat_create` | 0.3ms | Client pre-cached; chat creation is in-memory |
| `llm_api_call` | 3911ms | Network + inference + auto tool call + synthesis |
| `tool:get_events` | 4.9ms | Local JSON file search |
| **total** | **~3700ms avg** | **~55% faster than Baseline A** |

> [!IMPORTANT]
> Engine init time increased (312ms → 2168ms) because the Gemini client and personality are now pre-warmed at startup. This is a one-time cost; every query after pays nothing for either.

### Baseline C — After Latency Sprint (2026-05-06)
`gemini-2.5-flash`, system prompt shrunk (11.8k → 8.9k chars), `maximum_remote_calls=3`, server-side tool-call dedupe, streamed final answer via `send_message_stream`. Sample of representative queries:

| Query | Time-to-first-chunk | Total | Tool calls | Notes |
|:---|---:|---:|---:|:---|
| "What talks today?" (free-form, AFC) | ~0.8s | **~2.6s** | 1 | was 13–25s on `flash-lite` baseline |
| "What is the title of the Haueis talk?" | ~1.4s | **~2.0s** | 1 | |
| "Who is Hannes Leitgeb?" (multi-tool) | ~1.0s | **~3.9s** | 2 (search_people, search_graph) | |
| Calendar click, 1 event (AFC bypass) | ~0.8s | **~1.3s** | 0 (pre-resolved) | was 13.7s |
| Calendar click, 2 events (AFC bypass) | ~0.5s | **~1.9s** | 0 (pre-resolved) | was 18.5s |
| Calendar click, empty date | n/a | **~0s** | 0 (no LLM call) | was 19.3s |

**~5–10× speedup on tool-using queries.** Streaming makes the perceived improvement larger because the first chunk arrives within ~1s instead of waiting for the full response.

---

## 4. Known Bottlenecks
### A. LLM API Latency (2000–5000ms per call) 🔴
The dominant cost. ~95% of per-query latency on a steady-state request.

**Factors:**
- Number of automatic tool round-trips (each adds ~1500–2000ms)
- Prompt length (system instruction + tool descriptions)
- Network latency to Gemini API

**Diagnosis:** Check `llm_api_call` in logs. If it's > 4000ms with a single tool, Gemini is doing 2+ round-trips internally.

### B. Tool File I/O (1–5ms per tool call) 🟢
Every MCP tool call loads its JSON file from disk via `load_data()`. Currently fast (< 5ms each) because the files are small and the OS caches them after the first read. The module also keeps a manual `_data_cache` dict so repeated loads within the process are free.

| Tool | File | Measured Latency |
|:---|:---|:---|
| `search_people` | `people.json` | ~3–5ms |
| `get_events` | `raw_events.json` | ~4–5ms |
| `search_graph` | `graph/mcmp_jgraph.json` | ~1ms |
| `search_research` | `research.json` | ~1ms |
| `search_academic_offerings` | `academic_offerings.json` | ~1ms |

### C. Engine Startup (~2s, once per process) 🟡
`ChatEngine.__init__` pre-initialises the Gemini client (~1.9s), personality, and tool definitions. This is a one-time cost during app startup and does not affect per-query latency.

---

## 5. Optimization Playbook
Ranked by impact. Applied items are marked ✅.

### ✅ Priority 1 — Remove Unused RAG / `decompose_query` Pre-Call
- **Problem:** A full extra Gemini LLM call was made on every request to decompose the query into sub-queries for RAG vector search. With RAG gone, this was pure waste (~3.5s per request).
- **Fix:** Delete `decompose_query()`, `retrieve_with_decomposition()`, and `VectorStore` from `engine.py`.
- **Savings:** ~3.5s per request.

### ✅ Priority 2 — Cache Gemini Client at Startup
- **Problem:** `genai.Client()` was recreated inside `generate_response()` on every call. First-time import + client creation cost ~1.9s.
- **Fix:** Create once in `__init__` as `self._gemini_client`. Reuse for all calls.
- **Savings:** ~20ms per call; eliminates 1.9s first-call penalty.

### ✅ Priority 3 — Cache Personality and Tool Descriptions
- **Problem:** `load_personality()` read from disk and tool description strings were rebuilt on every call.
- **Fix:** Cache both in `__init__` as `self._personality` and `self._tools_description_str`.
- **Savings:** < 1ms per call (negligible, but cleaner).

### ✅ Priority 4 — Cache JSON Data Files in Memory
- **Action:** `load_data()` in `src/mcp/tools.py` uses a manual `_data_cache` dict (deliberately not `lru_cache` because the latter would cache `[]` results when a file is missing at first call).
- **Status:** Done; verified 2026-05-06.

### ✅ Priority 5 — Streaming Responses (2026-05-06)
- **Problem:** Users see a long blank pause before any text appears.
- **Fix:** `ChatEngine.generate_response_stream()` uses `chat.send_message_stream()`; AFC runs synchronously inside the SDK then the final answer streams. Streamlit consumes via `st.write_stream()` and a wrapper that closes the `st.status` box on the first chunk.
- **Savings:** First chunk arrives at ~0.5–1.5s (was ~13–25s wait for full response).

### Priority 6 — Model Selection for AFC Workloads (corrected 2026-05-06)
- **Original recommendation (now reversed):** Route simple queries to a lighter model like `gemini-2.0-flash-lite`.
- **Finding:** When the chatbot uses AFC, `flash-lite` is **slower** end-to-end than `flash` because it takes more sequential AFC steps to reach the same answer. The MCMP chatbot ran on `gemini-2.5-flash-lite` from 2026-04-28 → 2026-05-06; queries took 13–25s. Switching back to `gemini-2.5-flash` cut that to 2–4s with no quality regression.
- **Current recommendation:** Default to `gemini-2.5-flash` for AFC. Reach for `flash-lite` only if 429s become the binding constraint.
- **Caveat:** Per-call cost is ~5× higher on `flash` vs `flash-lite`, but in absolute terms it's still fractions of a cent per query for typical chatbot traffic.

### Priority 7 — System Prompt Caching (Gemini Context Cache) 🔲
- **Action:** Use Gemini's context caching API for the static portion of the system prompt (personality + tool descriptions), which rarely changes.
- **Trade-off:** Cache has a minimum token size limit; adds API complexity.

### Priority 8 — Limit Chat History Length 🔲
- **Symptom:** `llm_api_call` grows linearly with conversation length.
- **Action:** Cap `chat_history` to the last N messages before passing to the LLM.
- **Trade-off:** Very long conversations may lose early context.

### ✅ Priority 9 — Server-Side Dedupe of Identical Tool Calls (2026-05-06)
- **Symptom:** Some Gemini models speculatively repeated identical tool calls inside a single user query (e.g. `get_events(date_range="today", type_filter="talk")` fired twice in a row), doubling latency for no benefit.
- **Fix:** `MCPServer` keeps a per-request cache `(tool_name, frozen_args) -> result`; `reset_call_cache()` is called at the top of every `generate_response*`. Both `call_tool()` and `get_instrumented_tools()` (used by AFC) check the cache.
- **Savings:** Eliminates the duplicate-call class entirely.

### ✅ Priority 10 — Bypass AFC When Args Are Pre-Resolved Client-Side (2026-05-06)
- **Pattern:** UI flows where the tool argument is already known (calendar click, button-driven query, typeahead selection) should not pay for the model's tool-decision round-trip.
- **Fix:** In `app.py::render_calendar_response`, `get_events(start_date=iso, end_date=iso)` is called directly. Empty results render a static reply (zero LLM calls). Non-empty results are passed to `generate_response_stream` with `use_tools=False` and a synthesis-only prompt embedding the JSON.
- **Savings:** Calendar-click latency 13–19s → 1.3–1.9s for populated dates; instant for empty dates.

### ✅ Priority 11 — Reduce `maximum_remote_calls` from 10 to 3 (2026-05-06)
- **Symptom:** AFC could chain up to 10 tool calls per query, encouraging speculative chains and inflating token spend.
- **Fix:** `automatic_function_calling.maximum_remote_calls=3` covers the realistic pattern (one tool call → answer, plus one speculative retry).
- **Savings:** Caps worst-case latency and token spend per query.

### ✅ Priority 12 — `thinking_budget=0` for Tool-Using Calls
- **Action:** `ThinkingConfig(thinking_budget=0)` is set in the Gemini config. May be silently ignored when complex tool declarations are present (per python-genai #1842) — harmless when ignored, big win when honored.
- **Status:** Already in place; reaffirmed 2026-05-06.

### ✅ Priority 13 — Shrink the Personality Prompt (2026-05-06)
- **Action:** `prompts/personality.md` shrunk from 6541 → 3572 chars (~46% reduction). Identity / Tone / Behavior narrative tightened; load-bearing **format specs** (Person / Event / Academic block templates) preserved verbatim, including the in-prompt event example added during the same session to lock in the `- **Title:**` flat-bullet shape.
- **Savings:** System instruction down from 11858 → 8894 chars (~750 input tokens per call).

---

## 6. Adding New Instrumentation
When adding new pipeline stages or optimizing existing ones:

1. **Import** `log_latency` from `src/utils/logger.py`.
2. **Wrap** the code block with `with log_latency("descriptive_name"):`.
3. **Naming convention:** Lowercase with underscores for stages (`llm_api_call`), `tool:{name}` prefix for MCP tools.
4. **Do NOT use as a decorator** — `log_latency` is a `@contextmanager`, not a decorator.

```python
from src.utils.logger import log_latency

with log_latency("my_new_stage"):
    result = expensive_operation()
```

---

## 7. Verification Checklist
- [x] `log_latency` context manager implemented in `src/utils/logger.py`
- [x] `generate_response` and `generate_response_stream` instrumented in `src/core/engine.py`
- [x] `call_tool` instrumented per-tool in `src/mcp/server.py`
- [x] Per-request tool-call dedupe in `src/mcp/server.py` (`_call_cache`, `reset_call_cache`)
- [x] All latency entries use `[LATENCY]` prefix for easy grep filtering
- [x] No new dependencies (uses stdlib `time` and `contextlib`)
- [x] `scripts/profile_latency.py` available for isolated per-stage benchmarking
- [x] RAG / `decompose_query` removed — no wasted LLM pre-call
- [x] Gemini client and personality cached at engine startup
- [x] Default model `gemini-2.5-flash` (reverted from `flash-lite` on 2026-05-06)
- [x] Streaming via `send_message_stream` wired through to Streamlit
- [x] Calendar-click bypass (`render_calendar_response` in `app.py`) skips AFC
- [x] Baselines measured: A (2026-02-14), B (2026-03-10), C (2026-05-06)
