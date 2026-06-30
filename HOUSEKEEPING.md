# MCMP Chatbot Housekeeping Workflow
- status: active
- type: workflow
- description: Recurring stress-test and health-check protocol for the MCMP Chatbot — runs the Gemini MCP stress battery, the pytest suites, and verifies data freshness; appends a dated audit report.
- label: [core, agent]
- injection: excluded
- volatility: evolving
- scope: project-specific
- last_checked: 2026-05-05
<!-- content -->
This file is the operational housekeeping protocol for the MCMP Chatbot repository. Run it periodically (suggested cadence: every 2–4 weeks, or after any non-trivial change to `src/core/engine.py`, `src/mcp/`, the system prompt, or the Gemini model/parameters). Its purpose is to detect regressions in the LLM tool-calling behavior, the MCP tool surface, and the data freshness pipeline before they reach users.

The workflow has four concerns: (1) sanity checks on the codebase, (2) the live Gemini stress test that exercises every MCP tool against the real API, (3) a quick health check on the scraped data files, and (4) an append-only audit trail in this file. The stress test is the centerpiece — most regressions in this project surface as wrong tool selection, broken multi-tool chains, or subtle prompt-engineering drift, and only a live battery catches them.

**Execution model:** sequential — each phase has an explicit exit criterion. Phases 2 and 4 require a working `GEMINI_API_KEY`; phases 3 and 5 do not.

**Prerequisites:**
- Python environment with `requirements.txt` installed.
- `GEMINI_API_KEY` set in `.env` or `.streamlit/secrets.toml` (the stress test loads `.env` via `python-dotenv`).
- `WORKLOG.md` and `TODO_WORKFLOW.md` at the repo root for capturing notable events and deferred work.

---

## Phase 1 — Context Load

**Goal:** Load the prior baseline so this run has comparison points.

1. Read the **Latest Report** section at the bottom of this file. Note the previous run's stress-test pass count, average latency, pytest pass count, and any unresolved follow-ups.
2. Skim the most recent `WORKLOG.md` entries for changes that might affect this run — model swap, system-prompt edit, new MCP tool, scraper change. The diff vs. last housekeeping run is the contextual frame for interpreting today's results.
3. Confirm the toolchain is ready:
   - `python --version` (project assumes 3.11+).
   - `echo $GEMINI_API_KEY` returns a key, or one exists in `.env` / `.streamlit/secrets.toml`.

**Exit criterion:** Prior baseline loaded; key changes since last run identified; environment confirmed.

---

## Phase 2 — Pytest Suite

**Goal:** Verify the offline test suites still pass before spending live API quota.

```bash
pytest tests/ -v
```

The suite covers: the OpenAI-mocked engine path (`test_engine.py`), MCP server unit tests (`test_mcp.py`), graph correctness (`test_graph_correctness.py`), scraper logic (`test_scraper.py`), vector store (`test_vector_store.py`), and the live Gemini integration tests (`test_gemini.py` — auto-skipped if no `GEMINI_API_KEY`).

**Note:** `test_gemini.py` makes a small number of real API calls but is not the stress battery — it only checks that the engine produces a non-empty response on a few queries. The stress battery in Phase 3 is the substantive check.

**Remediation:**
- A new failure that didn't exist last run is the priority finding for this housekeeping pass — investigate the cause before continuing.
- A drop in test count without a documented justification is as suspicious as a new failure.

**Exit criterion:** Pytest exits 0, or every failure has a recorded explanation in this run's report.

---

## Phase 3 — Gemini MCP Stress Battery

**Goal:** Verify that every MCP tool fires correctly on representative queries, multi-tool chains work, the fallback cascade works, and the model handles ambiguous and missing-data cases gracefully.

```bash
python -m tests.stress_test_gemini 2>&1 | tee tests/reports/stress_$(date -u +%Y-%m-%d).log
```

The harness runs 13 cases covering every tool (`search_people`, `search_research`, `get_events`, `search_graph`, `search_academic_offerings`, `grep_data`, `fuzzy_search`), multi-tool chains, the fallback cascade, missing-name handling, misspelled-name handling (the `misspelled_person_name` case asserts the *corrected* name surfaces, whether via the `search_people` fuzzy fallback or an explicit `fuzzy_search` call), and YYYY-MM-DD date formatting. Each case verifies the expected tools fired and that the response is not an `Error: …` string. The harness exits 0 only if all cases pass.

**Save the full transcript.** The `tee` invocation above captures the run to `tests/reports/stress_YYYY-MM-DD.log`. Create the `tests/reports/` directory the first time. Keep at least the three most recent transcripts; older ones can be deleted.

**Interpreting results:**
- **All 13 PASS:** baseline preserved.
- **One or two transient `503` failures that recover on retry:** acceptable — Google-side spike, the engine's retry block (`engine.py`) handles them. Note the count in the report.
- **A repeatable `FAIL_TOOLS`:** the model is no longer selecting the expected tool for that query type. Common causes: system-prompt drift, a new tool added without updating the **TOOL SELECTION GUIDE** section in `engine.py`, or a model regression.
- **A repeatable `FAIL_RESPONSE_ERROR`:** an exception is being swallowed by the engine. Check `logs/` for the underlying cause.
- **Average latency drift > 25% vs. last run:** investigate. Possible causes: thinking-tokens silently re-enabled (verify with `usage_metadata.thinking_token_count`), AFC chain length increase, model slowdown.

**Remediation order:**
1. Re-run any single failing case standalone to rule out transient issues.
2. If still failing, check the prompt / tool-selection guide in `src/core/engine.py` and the relevant tool's `description` field in `src/mcp/server.py`.
3. If the failure is a content-correctness issue (right tool fired, wrong answer), it is most likely a data or graph-edge issue, not a model issue — file it in `TODO_WORKFLOW.md`.

**Exit criterion:** Stress battery passes 12/12, OR every failure is characterized and either fixed or recorded as a follow-up.

---

## Phase 4 — Data Freshness Check

**Goal:** Detect stale or corrupted scraped data before it produces wrong answers.

1. Inspect the modification timestamps of the structured data files:
   ```bash
   ls -la data/people.json data/research.json data/raw_events.json data/academic_offerings.json data/graph/mcmp_graph.md
   ```
   If the most recent of these is older than ~30 days, schedule a scrape:
   ```bash
   python scripts/update_dataset.py
   ```
2. Sanity-check counts (no schema needs to be assumed — just verify the files are non-empty and JSON-valid):
   ```bash
   python -c "import json; [print(f, len(json.load(open(f)))) for f in ['data/people.json','data/research.json','data/raw_events.json','data/academic_offerings.json']]"
   ```
   A sudden large drop in the number of entries vs. the prior report is a finding — the scraper may have failed silently. Note that per `README.md`, the dataset is **accumulating** — counts should only grow, never shrink. A shrink is a regression.
3. Spot-check `data/scraping_logs.json` for the most recent run's `"removed"` field — large numbers there mean the website hid entries during the last scrape, not that they were deleted from our dataset.

**Exit criterion:** All data files are present, JSON-valid, and counts are steady or higher than the prior report.

---

## Phase 5 — Report & Close

**Goal:** Leave an auditable trail so the next housekeeping run has a baseline.

1. **Demote the previous report.** Rename the existing `## Latest Report` heading to `## Previous Report`. Older `## Previous Report` blocks stay in place, separated by `---` dividers.
2. **Append a new `## Latest Report`** using the template at the bottom of this file. Fill every field. Use `n/a` for any phase that did not run rather than deleting the section — report shape stays stable across runs.
3. **File follow-ups in `TODO_WORKFLOW.md`** for anything that was found and not fixed. Findings must not live only in this report — `TODO_WORKFLOW.md` is the forward-looking entry point for the next agent.
4. **Bump `last_checked`** in this file's metadata header to today's date (UTC).
5. **Update `WORKLOG.md`** with a one-paragraph summary if anything notable happened (regression, fix, model swap, scraper failure). A clean run does not need a WORKLOG entry — that's what this report is for.

**Exit criterion:** New `## Latest Report` reflects today's run, deferrals are recorded in `TODO_WORKFLOW.md`, and `last_checked` is updated.

---

## Quick Reference — Housekeeping Checklist

```
[ ] Phase 1: Prior report read; recent WORKLOG entries skimmed; env confirmed
[ ] Phase 2: pytest tests/ — all green (or failures characterized)
[ ] Phase 3: stress battery — 13/13 PASS; transcript saved to tests/reports/
[ ] Phase 4: data files fresh, JSON-valid, counts steady-or-higher
[ ] Phase 5: Latest Report appended; follow-ups filed; last_checked bumped
```

---

## Latest Report

**Date:** 2026-05-05
**Trigger:** First run — bootstrapping the housekeeping workflow immediately after authoring HOUSEKEEPING.md, the model swap to gemini-2.5-flash-lite, and the new stress harness.
**Operator:** Claude (agent), pair with user

### Pytest
- Suite: 16 passed / 0 failed / 0 skipped (20.42s)
- Comparison vs. previous: n/a (first run — establishes baseline at 16)
- Notable failures: none

### Gemini stress battery
- Result: 12/12 PASS
- Average latency: 5.11s  (n/a — first run, baseline)
- Transient 503/429 retries observed: 0
- Transcript: tests/reports/stress_2026-05-05.log
- Tool-selection issues: none — every case fired the expected tool, including multi-tool chains and the fallback cascade (search_people → grep_data on the Bayesianism query).
- Content-correctness issues: 1 — `graph_org_question` ("Who leads the Chair of Logic and Philosophy of Language?") returns Godehard Link (Professor Emeritus) instead of Hannes Leitgeb. Root cause is **not** the model: it is the missing `data/graph/mcmp_graph.md` file (see Notable events). With the graph empty, the model falls back to `search_people` keyword-matching the unit string, which finds Godehard Link first.

### Data freshness
- Most recent scrape: 2026-05-05 (mtime on all four JSON files)
- Entry counts:
  - people.json: 82 entries (n/a — baseline)
  - research.json: 4 entries (n/a — baseline)
  - raw_events.json: 89 entries (n/a — baseline)
  - academic_offerings.json: 5 entries (n/a — baseline)
- Counts steady-or-higher: yes — first run, all counts captured as the baseline.
- **Missing artifact:** `data/graph/mcmp_graph.md` does not exist locally. `data/` is gitignored, so the graph was never tracked. `GraphUtils._load_graph()` silently no-ops when missing (see `src/core/graph_utils.py:18-19`), so `search_graph` runs against an empty graph. README documents this file as authoritative; it must be regenerated.

### Notable events
- **Missing graph file** is the load-bearing finding from this run. It is the single root cause of the chair-leadership content-correctness issue. Filed in TODO_WORKFLOW.md as `todo.regenerate_graph` (~15m fix: run `python scripts/update_dataset.py`).
- Latency on this run (5.11s) was substantially better than the second stress run during the model-swap session (10.24s) — likely a quieter Google-side hour. Future runs should treat 5–10s as the normal range, not the floor.
- This run had zero transient 503/429 retries; the engine's extended retry block (now matching both codes) was therefore not exercised. The previous session's first stress run did exercise it successfully — coverage exists, just not on this run.

### Files modified this run
- `tests/reports/stress_2026-05-05.log`: new — full stress test transcript saved
- `tests/reports/`: new directory — created on first run as documented
- `TODO_WORKFLOW.md`: appended `todo.regenerate_graph` task block
- `HOUSEKEEPING.md`: this report appended; `last_checked` already 2026-05-05 from authoring

### Follow-ups recorded in TODO_WORKFLOW.md
- `todo.regenerate_graph` — Rebuild missing `data/graph/mcmp_graph.md` so `search_graph` stops returning empty for chair/supervisor queries.

---

## Latest Report Template

Copy the block below and fill it in for each housekeeping run. The most recent block is `## Latest Report`; older blocks are renamed to `## Previous Report`.

````markdown
## Latest Report

**Date:** {{YYYY-MM-DD}}
**Trigger:** {{Routine cadence | post-model-swap | post-incident | post-merge | etc.}}
**Operator:** {{human or agent name}}

### Pytest
- Suite: {{N passed / M failed / K skipped}} ({{wall-clock seconds}})
- Comparison vs. previous: {{steady | +N tests | regression — describe}}
- Notable failures: {{none | list with one-line cause}}

### Gemini stress battery
- Result: {{12/12 PASS | N/12 — list failures}}
- Average latency: {{X.XXs}}  ({{delta vs. previous: +/- Y%}})
- Transient 503/429 retries observed: {{count}}
- Transcript: tests/reports/stress_{{YYYY-MM-DD}}.log
- Tool-selection issues: {{none | tool / case}}
- Content-correctness issues: {{none | brief description}}

### Data freshness
- Most recent scrape: {{YYYY-MM-DD}}
- Entry counts:
  - people.json: {{N}}  ({{delta vs. previous}})
  - research.json: {{N}}  ({{delta}})
  - raw_events.json: {{N}}  ({{delta}})
  - academic_offerings.json: {{N}}  ({{delta}})
- Counts steady-or-higher: {{yes | no — describe}}

### Notable events
- {{Surprises, root-caused issues, decisions made — or "none"}}

### Files modified this run
- {{Path: change | none}}

### Follow-ups recorded in TODO_WORKFLOW.md
- {{Title — short reason | none}}
````
