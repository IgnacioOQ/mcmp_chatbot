# TODO Workflow
- status: active
- type: plan
- id: plan.todo_workflow
- description: Cross-session task backlog; each task is self-contained and can be picked up by a coding agent with kb_mcp MCP tool access.
- label: [planning, agent]
- injection: informational
- volatility: evolving
- scope: general
- owner: agent
- last_checked: 2026-05-04
<!-- content -->

Cross-session task backlog. Tasks are added here when work started in a session cannot be completed immediately. Each task must be fully self-contained — a fresh agent should be able to pick it up using only the task body and the kb_mcp tools, with no additional context required.

**Agent rules (picking up tasks):**
1. Read each task in full before starting. If its preconditions are unmet, skip it and note the blocker.
2. After completing a task, delete its entire block from this file (from the `---` divider above the `##` header through the `---` divider below the last line of the task body).
3. After completing one or more tasks, assess whether a WORKLOG.md entry is warranted — see Phase 5 of `content/workflows/CODING_AGENT_MAIN_WORKFLOW.md`.
4. Confirm a task is still valid before executing; conditions may have changed since it was written.

**Adding tasks (session authors):**
- Copy the template below (without fences), fill in all fields, and insert it as a new `##` block above the Template section, preceded and followed by `---`.
- Be precise: include target file paths, specific tool calls, expected outcomes, and a verification step.
- Any `knowledge_base_update` call requires a current `content_hash` — capture it with a `knowledge_base_read` at execution time, not when writing the task.

---

## Execute Firebase Migration Plan
- status: todo
- type: task
- id: todo.firebase_migration
- description: Execute docs/FIREBASE_MIGRATION_PLAN.md — 8-phase migration from Streamlit to Firebase (Next.js App Hosting + FastAPI Cloud Run + Firestore). Phase 0 decisions locked; Phases 1–8 are todo.
- owner: agent
- estimate: 10h+
- blocked_by: []
- last_checked: 2026-05-05
<!-- content -->

**Context:** `docs/FIREBASE_MIGRATION_PLAN.md` is the authoritative plan. Phase 0 is `status: done`; Phases 1–8 are `status: todo`. No implementation has started. All steps, KB context loads, and the multi-session executing agent protocol are in the plan preamble — read it before acting.

**Preconditions:** Read `docs/FIREBASE_MIGRATION_PLAN.md` in full. Follow the executing agent protocol in its preamble (load KB context, find current position, mark tasks done as you go).

**Verification:** All phases 1–8 `status: done` in the plan; App Hosting URL serves the chat interface; `/admin` sign-in works for `ignacioojea@gmail.com`.

**On completion:** Delete this entire task block from TODO_WORKFLOW.md (from the `---` above the `##` header to the `---` below the last line).

---

## SSE Streaming for /chat (deferred v2 enhancement)
- status: todo
- type: task
- id: todo.sse_streaming
- description: Add Server-Sent Events streaming to the FastAPI /chat endpoint and the Next.js proxy + ChatPanel component, replacing the v1 blocking POST with token-by-token streaming.
- owner: agent
- estimate: 4h
- blocked_by: [todo.firebase_phase_1]
- last_checked: 2026-05-05
<!-- content -->

**Context:** The Firebase migration v1 (`docs/FIREBASE_MIGRATION_PLAN.md` Phase 4.1) uses a blocking POST for `/chat` to keep scope minimal. This task adds streaming as a follow-up once the full Firebase stack is live.

**Preconditions:** Firebase deployment fully verified (Phase 7 of migration plan complete). Read `src/core/engine.py` to assess current `ChatEngine.generate_response()` — check if `google-genai` streaming is already supported or needs to be added.

**Steps:**
1. Add a `generate_response_stream()` method to `src/core/engine.py` that yields tokens using the Gemini streaming API.
2. Add `GET /chat/stream` SSE endpoint in `firebase/backend/main.py` using FastAPI's `StreamingResponse`.
3. Update `firebase/frontend/src/app/api/chat/stream/route.ts` proxy route to forward the SSE stream (use `ReadableStream` pass-through — see `INFRASTRUCTURE_CHATBOT_TEMPLATE_REF.md` for the SSE pass-through pattern).
4. Update `ChatPanel` component to connect via `EventSource` or `fetch + ReadableStream`, display partial tokens as they arrive, and show tool-call events inline.

**Verification:** Chat input shows first token within 1–2s of submit; full response streams in progressively; tool icons appear as each MCP call is made.

**On completion:** Delete this entire task block from TODO_WORKFLOW.md.

---

## Migrate feedback from Google Sheets to Firestore (deferred)
- status: todo
- type: task
- id: todo.feedback_firestore
- description: Replace Google Sheets feedback storage with Firestore — update the FastAPI /feedback endpoint to write to a Firestore collection and update the admin panel to read feedback from Firestore.
- owner: agent
- estimate: 2h
- blocked_by: [todo.firebase_phase_1]
- last_checked: 2026-05-05
<!-- content -->

**Context:** Phase 0.6 of `docs/FIREBASE_MIGRATION_PLAN.md` deferred this. Google Sheets is kept in v1 to avoid migration risk. This task replaces it with Firestore once the stack is stable.

**Preconditions:** Firebase deployment fully live. Firestore `mcmp-firebase` project active.

**Steps:**
1. Add a `feedback` Firestore collection. Update Firestore security rules to allow authenticated admin users to read from `feedback` (extend `firestore.rules`).
2. Update `firebase/backend/main.py` `/feedback` endpoint to write `{timestamp, name, message}` to Firestore `feedback` collection instead of Google Sheets.
3. Remove `SHEETS_SA_JSON` and `SHEETS_ID` secrets from Secret Manager (after confirming feedback writes to Firestore in production).
4. Update `/admin` page to display feedback from Firestore via a new `/api/admin/feedback` proxy route.

**Verification:** Submit feedback from the chat page. Verify a Firestore document appears in the `feedback` collection. Verify it is visible in the `/admin` page.

**On completion:** Delete this entire task block from TODO_WORKFLOW.md.

---

## Task Template

Copy the block below (without the outer fences), fill in all fields, and insert it as a new `## [Task Title]` task block.

````markdown
## [Task Title]
- status: todo
- type: task
- id: todo.[short_id]
- description: One-sentence description of what this task accomplishes.
- owner: agent
- estimate: Xm
- blocked_by: []
- last_checked: YYYY-MM-DD
<!-- content -->

**Context:** Why this task exists and what triggered it. Include the KB path or repo file path it operates on.

**Preconditions:** Any state that must be true before starting (prior tasks complete, files present, etc.). Write `none` if there are none.

**Steps:**
1. (Include specific tool calls where possible, e.g., `knowledge_base_read(path="content/...", sections=["..."])`)
2. ...

**Verification:** How to confirm the task is complete (e.g., a grep that should return one match, a status field that should read `done`).

**On completion:** Delete this entire task block from TODO_WORKFLOW.md (from the `---` above the `##` header to the `---` below the last line).
````
