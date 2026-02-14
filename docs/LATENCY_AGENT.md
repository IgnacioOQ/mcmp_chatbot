# Latency Monitoring & Optimization Skill
- status: active
- type: agent_skill
- context_dependencies: {"conventions": "MD_CONVENTIONS.md", "engine": "src/core/engine.py", "server": "src/mcp/server.py", "logger": "src/utils/logger.py", "tools": "src/mcp/tools.py"}
<!-- content -->
This document defines the latency instrumentation in the MCMP Chatbot pipeline, documents known bottlenecks, and provides guidelines for diagnosing and optimizing response times.

---

## 1. Instrumentation Overview
- status: active
<!-- content -->
The pipeline uses a `log_latency` context manager (`src/utils/logger.py`) that wraps each stage with `time.perf_counter()` and logs elapsed milliseconds as `[LATENCY] stage_name: X.Xms`.

### Instrumented Stages

| Stage | File | What It Measures |
|:---|:---|:---|
| `total_generate_response` | `engine.py` | End-to-end time for a single request |
| `load_personality` | `engine.py` | Reading `prompts/personality.md` from disk |
| `build_tools` | `engine.py` | Building tool definitions + description strings |
| `format_history` | `engine.py` | Converting chat history to provider format |
| `llm_api_call` | `engine.py` | First LLM network call (all providers) |
| `llm_api_call_2` | `engine.py` | Second LLM call after tool results (OpenAI only) |
| `tool:{name}` | `server.py` | Individual MCP tool execution (e.g., `tool:get_events`) |

### How to Read the Logs

```bash
grep "\[LATENCY\]" mcmp_chatbot.log
```

Example output for a single request:
```
[LATENCY] load_personality: 3.2ms
[LATENCY] build_tools: 1.1ms
[LATENCY] format_history: 0.8ms
[LATENCY] tool:get_events: 87.3ms
[LATENCY] llm_api_call: 2341.5ms
[LATENCY] total_generate_response: 2476.2ms
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

---

## 2. Pipeline Anatomy
- status: active
<!-- content -->
A single request flows through these stages in order:

```
User Query (app.py)
  |
  v
generate_response() [total_generate_response]
  |
  +-- load_personality()      [load_personality]     ~3ms    (file I/O)
  +-- build tool definitions  [build_tools]          ~1ms    (in-memory)
  +-- format chat history     [format_history]       ~1ms    (in-memory)
  +-- LLM API call            [llm_api_call]         ~1-3s   (network)
  |     |
  |     +-- (Gemini auto-function-calling may trigger tool calls internally)
  |     +-- (OpenAI: explicit tool loop below)
  |
  +-- Tool execution          [tool:{name}]          ~5-100ms (file I/O)
  +-- LLM API call #2         [llm_api_call_2]       ~0.5-1.5s (network, OpenAI only)
```

### Provider Differences

| Provider | Tool Calling Model | Instrumentation Notes |
|:---|:---|:---|
| **Gemini** | `automatic_function_calling` (up to 5 round-trips) | `llm_api_call` includes tool execution time since Gemini handles it internally. `tool:{name}` still logs individually. |
| **OpenAI** | Explicit two-call loop | `llm_api_call` = first call, `tool:{name}` = each tool, `llm_api_call_2` = second call with results. |
| **Anthropic** | No tool calling implemented yet | Only `llm_api_call` is logged. |

---

## 3. Known Bottlenecks
- status: active
<!-- content -->

### A. LLM API Latency (1000-3000ms per call)

The dominant cost. Typically 50-70% of total request time.

**Factors:**
- Model size (`gemini-2.0-flash` vs `gemini-2.0-flash-lite`)
- Prompt length (system instruction + chat history + tool descriptions)
- Number of tool round-trips (Gemini auto-calling can trigger up to 5)

**Diagnosis:** Compare `llm_api_call` across requests. If it grows with conversation length, chat history size is the likely cause.

### B. Tool File I/O (5-115ms per tool call)

Every MCP tool call loads its JSON file from disk via `load_data()`:

| Tool | File | Size | Typical Latency |
|:---|:---|:---|:---|
| `get_events` | `raw_events.json` | ~150 KB | 50-115ms |
| `search_people` | `people.json` | ~230 KB | 25-65ms |
| `search_research` | `research.json` | ~12 KB | 5-20ms |
| `search_news` | `news.json` | ~18 KB | 5-20ms |
| `search_graph` | `mcmp_graph.md` | ~11 KB | 12-30ms |

> [!NOTE]
> `search_graph` is especially costly because it instantiates a new `GraphUtils()` on every call, re-loading and re-parsing the graph file each time.

### C. Personality Loading (2-5ms per request)

`load_personality()` reads `prompts/personality.md` from disk on every request. The file is static and rarely changes.

### D. Logging Overhead

Each `log_info()` call writes synchronously to both `mcmp_chatbot.log` (file) and stdout. Multiple log calls per request add up to ~20-60ms.

---

## 4. Optimization Playbook
- status: active
<!-- content -->
Ranked by impact (highest first). These are documented strategies for when latency becomes a problem.

### Priority 1: Reduce LLM Round-Trips

- **Symptom:** `llm_api_call` > 3000ms, or `total_generate_response` > 5000ms with Gemini auto-calling.
- **Action:** Reduce `maximum_remote_calls` from 5 to 2-3, or switch to explicit tool calling.
- **Trade-off:** Fewer tool calls may reduce answer quality for complex queries.

### Priority 2: Cache Data Files in Memory

- **Symptom:** `tool:get_events` or `tool:search_people` consistently > 50ms.
- **Action:** Add `@functools.lru_cache` to `load_data()` in `src/mcp/tools.py`, or use a singleton `DataManager` that loads files once at startup.
- **Trade-off:** Stale data until process restart or explicit cache invalidation.

### Priority 3: Cache GraphUtils Instance

- **Symptom:** `tool:search_graph` > 15ms.
- **Action:** Reuse the `GraphUtils` instance from `ChatEngine.graph_utils` instead of creating a new one per `search_graph()` call.
- **Implementation:** Pass the shared instance to the tool, or use a module-level singleton.

### Priority 4: Cache Personality

- **Symptom:** `load_personality` > 3ms consistently.
- **Action:** Read personality once at `ChatEngine.__init__` and store as `self.personality`.
- **Trade-off:** Requires restart to pick up personality changes.

### Priority 5: Limit Chat History Length

- **Symptom:** `llm_api_call` grows linearly with conversation length.
- **Action:** Cap `chat_history` to the last N messages (e.g., 10-20) before passing to the LLM.
- **Trade-off:** Very long conversations may lose early context.

---

## 5. Adding New Instrumentation
- status: active
<!-- content -->
When adding new pipeline stages or optimizing existing ones:

1. **Import** `log_latency` from `src/utils/logger.py`.
2. **Wrap** the code block with `with log_latency("descriptive_name"):`.
3. **Naming convention:** Use lowercase with underscores for stages (`llm_api_call`), and `tool:{name}` prefix for MCP tools.
4. **Keep it lightweight:** The context manager adds ~1 microsecond overhead. Do not nest excessively.

```python
from src.utils.logger import log_latency

with log_latency("my_new_stage"):
    result = expensive_operation()
```

---

## 6. Verification
- status: active
<!-- content -->
- [x] `log_latency` context manager implemented in `src/utils/logger.py`
- [x] `generate_response` instrumented with 5 stages in `src/core/engine.py`
- [x] `call_tool` instrumented per-tool in `src/mcp/server.py`
- [x] All latency entries use `[LATENCY]` prefix for easy grep filtering
- [x] No new dependencies (uses stdlib `time` and `contextlib`)
