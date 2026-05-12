# AI Agent Logs
- status: active
- type: log
- description: Append-only history of agent interventions, architectural changes, and feature implementations.
- injection: informational

<!-- content -->

## 2026-05-12 — KB scraping-doc cleanup: created local `docs/MCMP_SCRAPING_REF.md`, stripped MCMP blocks from `WEB_SCRAPING_SKILL.md`, deleted `SCRAPER_SKILL.md`
- **Task:** Mirror the Ayoreo cleanup pattern: the shared kb_mcp KB had MCMP-specific scraping content embedded in two `how-to` docs that are meant to be generic. Preserve everything MCMP-specific in this repo first, then strip the KB.
- **Outcome:** (1) Created `docs/MCMP_SCRAPING_REF.md` consolidating: LMU JSON API endpoints (events + news), individual-page DOM selectors (events + people), output schemas (events / people / news), the single-class `MCMPScraper` architecture, the URL-keyed accumulation policy, the `chair` vs `organizational_unit` field-alignment incident in `src/mcp/tools.py`, 404/departed-people handling, the `AGENT_LOGS.md` dataset-size logging protocol, and an MCMP-scoped verification checklist. (2) Surgically updated `content/how-to/WEB_SCRAPING_SKILL.md` via `knowledge_base_update`: removed `## People Profile Extraction (MCMP)`, `## MCMP Output Schemas`, `## Single-Class Scraper Architecture`, the `### 404 pages and the accumulation policy` subsection, and the `pytest tests/test_scraper.py -v` checklist line; rewrote the MCP field-name mismatch anti-pattern in abstract terms (`field_a`/`field_b` instead of the chair/organizational_unit incident). KB-side backup at `.kb_backups/2026-05-12_203556/`. (3) Deleted `content/how-to/SCRAPER_SKILL.md` from disk (entire doc was MCMP-specific by its own description); ran `manager/registry/sync_registry.py`, `src/backlinks_builder.py`, and `src/build_associations.py --apply` to update the indexes; manually cleared the lingering `SCRAPER_SKILL.md` reference from `WEB_SCRAPING_SKILL`'s `associations` array in `dependency_registry.json` (the rebuild script logged the removal but didn't persist it). Final `audit_registry.py`: 165 files on disk = 165 in registry, zero stale entries, zero broken deps.
- **Key decisions:** (1) Kept a generic-but-de-MCMP'd version of `## End-to-End Pipeline Verification` in the KB — the principle (scraper-writes vs MCP-reads schema drift) is genuinely transferable; only the project-specific incident details belong in the local repo. (2) Deleted `SCRAPER_SKILL.md` rather than genericizing it because every section was MCMP-specific by construction (LMU JSON URLs, MCMP DOM tables, `AGENT_LOGS.md` protocol) — genericizing would have left an empty shell duplicating `WEB_SCRAPING_SKILL.md`. (3) Preamble of `WEB_SCRAPING_SKILL.md` now cites both `AYOREO_SCRAPING_REF.md` and `MCMP_SCRAPING_REF.md` as examples of the project-local pattern.
- **KB changes:** Updated `content/how-to/WEB_SCRAPING_SKILL.md`. Deleted `content/how-to/SCRAPER_SKILL.md`. Updated `dependency_registry.json`, `backlinks_index.json`.
- **Follow-up:** None. The `KB_SANITY_RUN_LOG.md` entry that says `"WEB_SCRAPING_SKILL.md, SCRAPER_SKILL.md | Explicitly partitioned — keep both"` is now stale, but it's an append-only log so the newer generic-content principle supersedes it without needing a rewrite.

## 2026-05-12 — Regenerated institutional graph and fixed silent `build_graph` mkdir bug
- **Task:** TODO item `todo.regenerate_graph` flagged that `data/graph/mcmp_graph.md` and `mcmp_jgraph.json` were missing locally, causing `search_graph` to silently query an empty graph. Regression: "Who leads the Chair of Logic and Philosophy of Language?" returned Godehard Link (via `search_people` keyword fallback on the `unit` field) instead of Hannes Leitgeb. Also a soft prerequisite for Phase 3.6 of the Firebase migration plan — without a rebuild, Firestore would have been populated with an empty `graph` collection.
- **Outcome:** Ran `python scripts/update_dataset.py`. Data scrape succeeded (97 events, 82 people, 4 research items, 6 general items, 13 changes logged). The graph build step at the end failed with `FileNotFoundError: data/graph/mcmp_graph.md`. Root cause: `src/utils/build_graph.py:237-238` opens the markdown path for write without ensuring the parent directory exists, and the scraper's `save_to_json()` (`src/scrapers/mcmp_scraper.py:1136-1140`) wraps the call in a try/except that logs the error but does not propagate it — so the broken graph build was invisible to the rest of the pipeline. Since `data/` is gitignored, every fresh checkout would silently lose the graph. Fix: added `md_path.parent.mkdir(parents=True, exist_ok=True)` before the write at `src/utils/build_graph.py:238`. Re-ran `python -m src.utils.build_graph` standalone → produced 86 nodes / 49 edges. Direct `GraphUtils.get_subgraph("Chair of Logic and Philosophy of Language")` now returns `Prof. DDr. Hannes Leitgeb leads Chair of Logic and Philosophy of Language (Head of Chair)`. Regression resolved.
- **Key decisions:** (1) Fixed `build_graph.py` at the source rather than removing the scraper's exception swallow. The swallow is intentional — graph build is non-critical relative to the data scrape itself, and one shouldn't fail the other. But the underlying open-without-mkdir bug is a real fault that bites on every fresh checkout, so it's correct to fix at the open site. (2) Skipped the LLM stress test (`graph_org_question`); the direct `GraphUtils` query is structural proof that the graph data is correct, and the stress test would burn Gemini tokens for marginal additional confidence.
- **KB changes:** None — repository-specific bug fix.
- **Follow-up:** Consider running `python -m tests.stress_test_gemini` at the next housekeeping pass for end-to-end belt-and-suspenders verification.

## 2026-05-06 — Moved project-specific latency content out of the KB
- **Task:** User flagged that knowledge-base docs should be repository-agnostic; `content/reference/LATENCY_REF.md` was the worst offender (specific MCMP file paths, MCMP tool names, project-specific baselines, per-priority status of *this* repo). The original was already project-specific despite its `scope: general` metadata; today's latency-sprint updates made it more so.
- **Outcome:** Created `docs/LATENCY.md` in this repo with the full project-specific content (instrumentation, Baselines A/B/C, all 13 priorities, verification checklist), plus an explicit pointer to `content/how-to/GEMINI_CHATBOT_LATENCY_SKILL.md` (the genuinely repo-agnostic companion in the KB) for the transferable principles. The split is now clean: project state lives here; transferable lessons live in the KB.
- **Key decisions:** (1) Did not modify `LATENCY_REF.md` in the KB — the user took ownership of cleaning up the KB side themselves, including any other docs that may have the same problem (e.g. `MCP_AGENT_EXTENDED_EXPLANATION.md`, `PERSONALITY_SKILL.md`, `GCLOUD_SKILL.md`). (2) `docs/LATENCY.md` uses the project's lighter metadata style (matches `docs/MCP_AGENT_EXTENDED.md`) rather than the full MDDIA schema used in the KB. (3) Cross-references inside the KB (`MCP_SKILL.md`, `GEMINI_ERROR_HANDLING_SKILL.md`, `MCP_AGENT_EXTENDED_EXPLANATION.md`, `ADK_CHATBOT_SKILL.md`) currently still point at `LATENCY_REF.md`; left untouched since the user is handling KB cleanup.
- **KB changes:** None this turn — by design.
- **Follow-up:** When the user finishes the KB-side cleanup, the See-also pointers above may need their `LATENCY_REF.md` references updated or removed.

## 2026-05-06 — Latency sprint: 5–10× speedup across all chatbot paths
- **Task:** End-to-end response felt slow (13–25s per tool-using query). User asked for a multi-front pass to fix it.
- **Outcome:** Six independent levers shipped, each measured: (1) **Default model** swapped from `gemini-2.5-flash-lite` back to `gemini-2.5-flash` (was changed on 2026-04-28 to escape 429s, but `flash-lite` is *slower* end-to-end on AFC workloads — confirmed empirically). (2) **AFC limit** `maximum_remote_calls` reduced 10 → 3, plus `thinking_budget=0` reaffirmed. (3) **Server-side dedupe** of identical tool calls in `MCPServer` with per-request cache cleared at the top of every `generate_response*`; eliminates the duplicate-call class. (4) **Personality prompt** shrunk 6541 → 3572 chars (~46%); the `Person` / `Event` / `Academic offering` block format specs and the worked event example are preserved verbatim because they are load-bearing. System instruction now ~750 input tokens lighter per call. (5) **Streaming**: new `ChatEngine.generate_response_stream()` uses `chat.send_message_stream`; `app.py` consumes via `st.write_stream` with a wrapper that closes the `st.status` box on the first chunk. First chunk now arrives at ~0.5–1.5s. (6) **Calendar-click AFC bypass**: `app.py::render_calendar_response` calls `get_events(start_date=…, end_date=…)` directly. Empty result → static reply (zero LLM calls). Non-empty → synthesis-only prompt with the JSON embedded and `use_tools=False`. Measured: free-form query 13–25s → 2–4s; calendar-click 13.7–18.5s → 1.3–1.9s; calendar-click empty date 19.3s → ~0s. `tests/test_mcp.py` + `tests/test_engine.py` 4/4 pass throughout.
- **Key decisions:** (1) Levers 1–6 are layered — each one helps independently, but the calendar-click bypass (lever 6) gives the biggest win for the most common UI flow because it skips the model's tool-decision round-trip entirely. (2) Per-request scope for the dedupe cache (cleared at the top of every `generate_response`) avoids stale-data risk if the underlying JSON is updated between sessions. (3) Streaming retry: the 429/503 retry only wraps the call that establishes the stream; once chunks flow, partial output cannot be cleanly retried — propagate. (4) The shrunk personality prompt was tested against three representative queries before being committed; the format specs survived intact and the LLM's output structure did not drift. (5) The `flash-lite` reversal corrects a recommendation that was in `LATENCY_REF.md` Priority 6 ("route simple queries to flash-lite for cost"); for AFC tool-using workloads the lighter tier takes more sequential steps and ends up *slower*.
- **KB changes:** Imported new `content/how-to/GEMINI_CHATBOT_LATENCY_SKILL.md` (general transferable lessons across Gemini chatbot projects). Updated `content/reference/LATENCY_REF.md`: added Baseline C with measured numbers, marked Priorities 4 (data file caching) and 5 (streaming) ✅, corrected Priority 6 (flash-lite default reversed), and added Priorities 9–13 (dedupe, AFC bypass, AFC limit, thinking_budget, personality shrink). `last_checked` bumped to 2026-05-06.
- **Follow-up:** Run `python -m tests.stress_test_gemini` to validate the new model + AFC limit on the full battery (the 12 cases that exercise every tool and chain). Priorities 7 (Gemini context cache for the static prompt portion) and 8 (chat-history truncation) in `LATENCY_REF.md` remain open — they were not blocking and have diminishing returns over what shipped today.

## 2026-05-06 — Fixed `get_events` returning the wrong title to the LLM
- **Task:** User reported the chatbot systematically fails to state the actual talk title (e.g. "The productive polysemy of scientific language" for today's Haueis talk), even though the dataset entry has it.
- **Outcome:** Root cause was in `src/mcp/tools.py::get_events`: the dataset has a dedicated `talk_title` field, but the tool returned only `title` (the listing header, e.g. "Talk: Philipp Haueis (Bielefeld)"). The talk's actual title only survived as a `"Title: ..."` prefix inside the long `description` string, which the LLM was failing to parse out reliably. **First attempt** added `talk_title` as a separate field in the result dict and updated the docstring to instruct the LLM to prefer it. End-to-end test against three phrasings showed this was insufficient: when asked directly ("What is the title…?") the model surfaced `talk_title`, but for list-style queries ("What talks are happening today?") it still anchored on `title` as the canonical heading. **Final fix** collapses the two fields server-side: `title` itself is now `talk_title or listing_header`. The speaker's name and affiliation are already in `speaker`, so the listing-header form ("Talk: <Speaker>") is recoverable when needed and was redundant in the result anyway. Re-tested the same three phrasings post-fix — all three now lead with the talk's actual title; workshop entries (no `talk_title`) correctly fall back to the listing header. `tests/test_mcp.py` 3/3 passes.
- **Key decisions:** (1) Collapsed `title` rather than keeping both fields and asking the LLM to choose. The first attempt proved that prompt-level guidance ("prefer X when non-empty") is unreliable when a field is *named* `title` — the model's prior over field names is stronger than docstring instructions. The right fix is to make the canonical name resolve to the canonical value at the source. (2) Type-filter and query-text matching now run against `listing_header + talk_title + abstract + description` so type filters like `"Talk"` (which only appear in the listing header) and speaker-name queries like `"Haueis"` continue to work even though the surfaced `title` no longer contains them. (3) No prompt-level change — fixing the data shape is structurally cleaner than patching the system prompt.
- **KB changes:** None — project-specific fix.
- **Follow-up:** Worth a regression case in `tests/stress_test_gemini.py` that asks for a specific upcoming talk and verifies the response contains the actual talk title (rather than the listing header). Would catch any future tool-shape regression. Not done in this session.

## 2026-05-05 — Gemini model + generation parameters tuned for cost and consistency
- **Task:** Reconsider the Gemini model choice and generation parameters in light of `MCP_SKILL.md` and `GEMINI_ERROR_HANDLING_SKILL.md` guidance. The previous setup (`gemini-2.5-flash`, default temperature, default thinking budget) was chosen on 2026-04-28 to escape 429s but was not revisited for cost or determinism.
- **Outcome:** Switched default model from `gemini-2.5-flash` to `gemini-2.5-flash-lite` (skill-recommended default; cheaper and less prone to throttling). Added `temperature=0` and `thinking_config=ThinkingConfig(thinking_budget=0)` to the Gemini `GenerateContentConfig` in `src/core/engine.py`. Centralized the model name as `DEFAULT_GEMINI_MODEL` in `engine.py` and replaced both hardcoded references in `app.py` with the import — eliminates the three-place drift that existed before.
- **Key decisions:** (1) `flash-lite` chosen over `flash` because the chatbot mostly does extraction and light synthesis on top of MCP tool output, which doesn't need flash's stronger reasoning. (2) `thinking_budget=0` set despite the known caveat (silently ignored when tool declarations + complex system prompt are present per python-genai #1842) — harmless when ignored, takes effect when honored, and documents intent. (3) `temperature=0` matches the OpenAI branch and improves consistency for factual Q&A. (4) AFC settings (`maximum_remote_calls=10`, `mode="AUTO"` implicit) left unchanged per skill warning against `mode="ANY"`.
- **KB changes:** None — both skill documents already cover this scenario accurately.
- **Follow-up:** Monitor for any 429s on flash-lite and for any quality regression on synthesis-heavy queries. If thinking-disabled is being silently ignored, `usage_metadata.thinking_token_count` from a response will reveal it; consider logging this if cost monitoring becomes important.

## 2026-05-05 — First housekeeping run: surfaced missing graph artifact
- **Task:** Execute the newly-authored `HOUSEKEEPING.md` end-to-end as its first run, establishing the baseline for future comparisons.
- **Outcome:** All 5 phases completed. Pytest: 16/16 passed (20.4s). Gemini stress battery: 12/12 PASS (avg 5.11s, zero transient retries) — transcript saved to `tests/reports/stress_2026-05-05.log`. Data freshness check: all four JSON files are present, JSON-valid, and dated today (people=82, research=4, raw_events=89, academic_offerings=5 — captured as baseline). The Latest Report block in `HOUSEKEEPING.md` was populated, and the prior content-correctness suspicion ("graph_org_question" returns wrong chair leader) was root-caused.
- **Key decisions:** (1) Recorded the missing-graph finding as a `todo.regenerate_graph` task block in `TODO_WORKFLOW.md` rather than fixing it inline — the user should decide whether to run the scraper now (which also rewrites all four data JSONs) or to leave the data files untouched and only rebuild the graph. (2) The chair-leadership issue I previously flagged as "content-correctness, orthogonal to model" turns out to have a single root cause: `data/graph/mcmp_graph.md` is missing on disk, `data/` is gitignored, and `GraphUtils._load_graph()` silently no-ops on missing files — so `search_graph` is degraded to empty results, and the model falls back to `search_people` keyword-matching, which surfaces Godehard Link first. Single fix should resolve the regression.
- **KB changes:** None.
- **Follow-up:** `todo.regenerate_graph` is the actionable item. After it is executed, the next housekeeping run should re-run the stress battery and confirm `graph_org_question` returns Hannes Leitgeb.

## 2026-05-05 — Authored HOUSEKEEPING.md at repo root
- **Task:** Create a recurring housekeeping protocol for the repo, focused on stress-testing the chatbot's functionalities and saving the results.
- **Outcome:** `HOUSEKEEPING.md` created at the repo root (~1500 words). Five-phase workflow: (1) context load, (2) pytest suite, (3) Gemini MCP stress battery via `python -m tests.stress_test_gemini` with transcript captured to `tests/reports/stress_<date>.log`, (4) data freshness check on the four scraped JSONs, (5) demote previous report → append a new `## Latest Report` block. Includes a fillable report template at the bottom. Metadata follows MD_CONVENTIONS for workflow type: root-only metadata, `<!-- content -->` separator, `label: [core, agent]`, `injection: excluded`, `scope: project-specific`. The filename is exempt from the `_SUFFIX` convention per MD_CONVENTIONS' explicit allow-list of root operational files.
- **Key decisions:** (1) Workflow centerpiece is the live stress battery, not static checks — the project's most likely regressions are LLM tool-selection drift and prompt regressions, which only a live battery catches. (2) Transcripts go to `tests/reports/` (gitignore decision left to user — small text logs, low risk either way). (3) The "Latest Report" pattern from `HOUSEKEEPING_TEMPLATE.md` is preserved verbatim so future runs have a stable baseline shape. (4) Suggested cadence is 2–4 weeks or after any change to `engine.py` / `src/mcp/` / system prompt / Gemini config — explicit triggers, not just calendar time.
- **KB changes:** None — this is a working-repo file, not a KB file.
- **Follow-up:** First housekeeping run is not yet executed; the file's `## Latest Report` section will only be populated on the first real run. The graph-correctness issue from the earlier stress test (chair-leadership question returns wrong person) remains an open item that should surface in the first housekeeping run's "Notable events".

## 2026-05-05 — Stress-tested gemini-2.5-flash-lite + extended retry to 503
- **Task:** Validate that the model swap to `gemini-2.5-flash-lite` does not regress MCP tool selection, multi-tool chaining, or fallback behavior. Add a reusable stress-test harness so future model/parameter changes can be re-validated.
- **Outcome:** Created `tests/stress_test_gemini.py` — a 12-case live-API battery covering every MCP tool (`search_people`, `search_research`, `get_events`, `search_graph`, `search_academic_offerings`, `grep_data`), date-range queries, multi-tool chains, fallback cascade, and missing-name handling. The harness uses the existing `status_callback` hook to capture which tools fired and verifies expected tools, response content, and absence of `Error:` responses. Final result: **12/12 PASS** at avg 10.24s/query. First run produced two 503 UNAVAILABLE failures; this exposed that the Gemini retry block in `engine.py` only handled `429` despite the skill doc listing `503` as transient. Extended the retry logic to retry on both `429` and `503` and added a 5s first delay (now `[5, 15, 30]`); re-run passed cleanly.
- **Key decisions:** (1) Stress test runs against the live API rather than mocks — the only thing worth validating after a model swap is real tool-calling behavior. (2) Verdict logic explicitly checks for the `"Error:"` prefix the engine returns on swallowed exceptions, since a counted-as-PASS test can hide a real failure if just one tool fired before the error. (3) `503` retry uses the same delay schedule as `429`; both are characterized in the skill as transient Google-side issues. (4) One observed correctness issue is **not** model-related: the "who leads the Chair of Logic and Philosophy of Language" query surfaced Godehard Link (emeritus, similarly-named chair) instead of Hannes Leitgeb. This is a graph-data/prompt issue worth a separate look but is orthogonal to the model swap.
- **KB changes:** None — `GEMINI_ERROR_HANDLING_SKILL.md` already documents 503 as transient; the engine simply hadn't implemented that guidance yet.
- **Follow-up:** (a) Investigate why `search_graph` doesn't surface Leitgeb as leader of the Chair of Logic and Philosophy of Language — likely a missing `leads`/`heads` edge in `data/graph/mcmp_graph.md` or a prompt-level issue around picking the right person from a chair's affiliates. (b) Consider running the stress test in CI or as a pre-deploy gate when changing model/parameters.

## 2026-05-05 — Firebase migration plan: MD_CONVENTIONS audit and multi-session hardening
- **Task:** Audit `docs/FIREBASE_MIGRATION_PLAN.md` for MD_CONVENTIONS compliance and add multi-session support (memory, WORKLOG, and KB knowledge capture).
- **Outcome:** Plan updated with: (1) Executing Agent Protocol in preamble — 6-step guide for any agent picking up the plan across sessions; (2) `owner: agent` and `last_checked` added to all 9 phase-level nodes; (3) Phase 8.3 corrected — `TODO_WORKFLOW.md` already existed; (4) Phase 8.2 extended with memory file update instruction; (5) Phase 8 renamed to include "Knowledge Capture"; (6) Tasks 8.4 (KB doc update post-implementation) and 8.5 (KB performance feedback) added per MD_CONVENTIONS BP #11. `TODO_WORKFLOW.md` updated: `todo.firebase_phase_1` replaced with a leaner `todo.firebase_migration` entry pointing to the plan as authoritative source.
- **Key decisions:** Replaced the Phase 1-only `todo.firebase_phase_1` task with a single `todo.firebase_migration` entry — detailed per-phase steps live in the plan itself, not in the TODO entry. Knowledge capture tasks (8.4–8.5) are marked mandatory in the executing agent protocol, not optional.
- **KB changes:** None.
- **Follow-up:** Begin Phase 1 of `docs/FIREBASE_MIGRATION_PLAN.md` in next session. Entry point: `todo.firebase_migration` in `TODO_WORKFLOW.md`.

## 2026-05-05 — Firebase migration plan authored
- **Task:** Research and write a detailed, phased migration plan to move the MCMP Chatbot from Streamlit to Firebase.
- **Outcome:** `docs/FIREBASE_MIGRATION_PLAN.md` created — 8 execution phases, ~50 tasks, all key architecture decisions locked. No implementation started.
- **Key decisions:** Next.js 14 SSR on Firebase App Hosting (following Chatbot Template canonical pattern); FastAPI on Cloud Run (IAM-only, OIDC proxy from App Hosting); Firestore for all scraped data; Cloud Run Job + Cloud Scheduler (weekly) for the scraper; Google Sheets for feedback (unchanged); new isolated GCP project `mcmp-firebase` at org root; production branch `firebase-branch`; ChromaDB dropped from Firebase build; public chat with Google-auth-gated `/admin` panel.
- **KB changes:** None — existing KB documents (`DEPLOY_FIREBASE_WORKFLOW.md`, `INFRASTRUCTURE_CHATBOT_TEMPLATE_REF.md`, `FIREBASE_DEFINITIONS_REF.md`) provided all necessary guidance.
- **Follow-up:** Begin Phase 1 (repo scaffold) in next session. See `docs/FIREBASE_MIGRATION_PLAN.md` for full task tree.

## 2026-04-28 — Switch to gemini-2.5-flash to resolve persistent 429 errors
- **Task:** Diagnose and fix persistent `429 RESOURCE_EXHAUSTED` errors from the Gemini API that were not resolved by the existing 15s/30s retry logic.
- **Outcome:** Confirmed quotas and retry logic were not the issue — the throttling was sustained beyond the 45s retry window. Switched model from `gemini-2.0-flash-lite` to `gemini-2.5-flash` in `app.py` (two call sites) and the default in `src/core/engine.py`. Error resolved immediately.
- **Key decisions:** `gemini-2.5-flash` is significantly more expensive (uses thinking tokens by default) but was the only available upgrade path since `flash-lite` was already the cheapest tier. This also partially addresses the follow-up from 2026-04-22 — a more capable model is now in use, though cost should be monitored.
- **KB changes:** None — `content/how-to/GEMINI_ERROR_HANDLING_SKILL.md` already covered this scenario accurately.
- **Follow-up:** Monitor token costs with `gemini-2.5-flash`. If costs are too high, consider switching back to `gemini-2.0-flash` once throttling clears, or upgrading quota on the AI Studio project.

---

## 2026-04-22 — Gemini tool-calling reliability investigation and fix
- **Task:** Diagnose why the chatbot was skipping MCP tool calls for date-based event queries after switching from `gemini-2.0-flash` to `gemini-2.0-flash-lite`.
- **Outcome:** Added an explicit system prompt rule in `_build_tools_description_str()` (`engine.py`) mandating `get_events` for any specific date or date-range query. Also trialled `tool_config` with `mode="ANY"` (Gemini `FunctionCallingConfig`) to force tool use, but reverted it after it caused an infinite tool-calling loop — the model called tools on every turn including after receiving results, exhausting `maximum_remote_calls=10` per request. Final working state: `gemini-2.0-flash-lite` with `mode="AUTO"` (default) and stronger system prompt instructions.
- **Key decisions:** `mode="ANY"` is incompatible with Automatic Function Calling (AFC) — it prevents the model from ever generating a final text response. `gemini-2.0-flash` was tested but hits 429 rate limits under free-tier usage. `gemini-2.0-flash-lite` + prompt engineering is the current pragmatic compromise.
- **KB changes:** `content/reference/MCP_TOOLS_REF.md` updated — added subsection 5.D documenting the `mode="ANY"` infinite loop pitfall and the correct `mode="AUTO"` approach.
- **Follow-up:** Tool-calling reliability with `gemini-2.0-flash-lite` remains imperfect for date queries. If rate limits are resolved (paid tier or quota increase), switching to `gemini-2.0-flash` would be the cleanest fix.

---

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

## [2026-04-20] 429 Errors — Resolved ✅

**Agent**: Claude (Sonnet 4.6)
**Task**: Investigate and mitigate `429 RESOURCE_EXHAUSTED` errors from the Gemini API.

### Root Cause (Full)
Two compounding issues:
1. The `GEMINI_API_KEY` in `.streamlit/secrets.toml` had expired (returned `400 API_KEY_INVALID`). A new key was generated and applied to both `.env` and `secrets.toml`.
2. `gemini-2.0-flash` was experiencing a model-level service degradation returning persistent 429s on `generateContent` — confirmed by `gemini-2.0-flash-lite` and `gemini-2.5-flash` succeeding on the same key/project. `gemini-2.0-flash-lite` was verified to support the full MCP tool chain and selected as the default.

### Resolution
- Default model changed from `gemini-2.0-flash` → `gemini-2.0-flash-lite` in `app.py` (both call sites) and `src/core/engine.py` (default parameter).
- New API key applied to `.env` and `.streamlit/secrets.toml`.
- Exponential backoff retry added to `chat.send_message()` (delays: 15s / 30s on 429).
- Removed unused `anthropic` import and dependency.

### Open Issue — High GenerateContent Latency
Cloud Console shows `GenerativeService.GenerateContent` p99 latency of ~19.5 seconds. Likely caused by multi-step tool-calling chains (up to `maximum_remote_calls=10`). Worth profiling.

### Open Issue — Revert model when degradation clears
Switch back to `gemini-2.0-flash` once the model-level degradation resolves. Check [status.cloud.google.com](https://status.cloud.google.com).

### Changes
- `src/core/engine.py`: Added `import time`; retry loop on 429 (15s/30s delays); default model → `gemini-2.0-flash-lite`; removed `anthropic` import.
- `app.py`: Default model → `gemini-2.0-flash-lite`.
- `requirements.txt`: Removed `anthropic`.

---

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

### Resolution

- **Root cause confirmed**: `data/academic_offerings.json` was gitignored (the entire `data/` directory is excluded) so it was never deployed to the server (`/home/ignacio/mcmp_chatbot/data/academic_offerings.json`). The debug log confirmed `path_exists=False` on every tool call.
- **Fix**: Added `!data/academic_offerings.json` to `.gitignore` (alongside the existing `!data/scraping_logs.json` exception) and committed the file to the repository. The server pulls it via `git pull` like all other code changes.
- **Verified**: Chatbot now returns the full MA program block with link when asked "talk to me about the MA program".

---

### All Code Changes Made
- `src/scrapers/mcmp_scraper.py`: Added constants, `self.academic_offerings`, `scrape_academic_offerings()`, `_scrape_bachelor_details()`, `_scrape_master_details()`, extended `save_to_json()` and `_log_changes()`.
- `scripts/update_dataset.py`: Added `argparse`, `should_scrape_academic_offerings()`, `--scrape-offerings` flag.
- `src/mcp/tools.py`: Added `search_academic_offerings()`, added `academic_offerings` to `_GREP_DB_MAP`, replaced `lru_cache` with `_data_cache` dict.
- `src/mcp/server.py`: Imported and registered `search_academic_offerings` in tools dict and `list_tools()`.
- `src/core/engine.py`: Updated tool selection guide, bumped `maximum_remote_calls` to 10.
- `prompts/personality.md`: Added academic offering block format.
- `data/academic_offerings.json`: Created and committed to repo.

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
