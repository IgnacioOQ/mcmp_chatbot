# MCMP Chatbot — Firebase Migration Plan
- status: todo
- type: plan
- id: mcmp_firebase_migration
- description: Multi-phase plan migrating the MCMP Chatbot from Streamlit to Firebase — Next.js SSR on App Hosting, FastAPI backend on Cloud Run, Firestore data layer, weekly Cloud Run scraper job, and public chat with Google-auth-gated admin panel.
- label: [planning, infrastructure, frontend, backend]
- injection: informational
- volatility: evolving
- scope: project-specific
- last_checked: 2026-05-05
<!-- content -->
This plan migrates the MCMP Chatbot from its current Streamlit deployment to a production-grade Firebase stack modelled on the Chatbot Template reference implementation (`INFRASTRUCTURE_CHATBOT_TEMPLATE_REF.md` in the knowledge base). The existing Streamlit code (`app.py`, `src/`, `data/`) is preserved untouched throughout the entire migration. All new code lives under `firebase/` in the same repository and deploys from a dedicated `firebase-branch` production branch into a new isolated GCP project `mcmp-firebase`.

The target architecture is: **Next.js 14 SSR on Firebase App Hosting** (public frontend + admin-gated `/admin` page) calling a **FastAPI service on Cloud Run** (IAM-only, invoked server-side via OIDC by App Hosting). Scraped data lives in **Firestore** (replacing local JSON files). A separate **Cloud Run Job** triggered weekly by Cloud Scheduler runs the existing MCMP scraper and writes to Firestore, replacing the fragile `>24h auto-refresh` hack. ChromaDB is dropped. Feedback continues via Google Sheets from the FastAPI backend.

The migration preserves every Streamlit UI feature: the interactive month calendar (grid, event-day dots, click-to-query), the Events This Week sidebar list, the chat with live MCP tool-call status icons, and the feedback form. An `/admin` panel is added, gated behind Google sign-in with email allowlist.

**Operating account (locked 2026-05-12):**
The entire Firebase deploy runs under the Google Workspace account `eikasia@eikasia.com` — NOT `ignacioojea@gmail.com`. The new `mcmp-firebase` GCP project lives at the **eikasia.com org root**, billing is on the eikasia organization, and all `gcloud` / `firebase` CLI commands in this plan must be executed while authenticated as `eikasia@eikasia.com`. Before starting any Phase 2+ task:
```bash
gcloud auth login eikasia@eikasia.com
gcloud config set account eikasia@eikasia.com
gcloud auth application-default login   # also as eikasia
firebase login --reauth                 # also as eikasia
```
Verify with `gcloud config get-value account` (must return `eikasia@eikasia.com`) before running provisioning commands. Pre-flight values to capture once authenticated:
- `gcloud organizations list` → record `<EIKASIA_ORG_ID>` (12-digit number) used in Phase 2.1.
- `gcloud billing accounts list` → record `<EIKASIA_BILLING_ACCOUNT_ID>` used in Phase 2.1.

The existing `mcmp-chatbot` GCP project (owned by `ignacioojea@gmail.com`) and its Streamlit Cloud deployment remain entirely untouched.

**Context loads for executing agents:**
> `mcp__kb_mcp__knowledge_base_read(path="content/reference/INFRASTRUCTURE_CHATBOT_TEMPLATE_REF.md")` — IAM bindings, SA names, Cloud Run spec, service URLs pattern.
> `mcp__kb_mcp__knowledge_base_read(path="content/how-to/INFRASTRUCTURE_CHATBOT_TEMPLATE_SKILL.md")` — deploy, log-reading, and cost-management runbooks.
> `mcp__kb_mcp__knowledge_base_read(path="content/workflows/DEPLOY_FIREBASE_WORKFLOW.md")` — Firebase CLI, Hosting, Firestore, Auth setup procedures.

**Executing agent protocol (multi-session work):**
1. **Load context:** Run the three context-load commands above before doing anything else in the session.
2. **Find current position:** Scan this file for the first `status: todo` phase. Within it, find the first `###` task whose `blocked_by` dependencies are all `status: done` (or absent).
3. **During execution:** After completing each `###` task, edit this file — set `status: done` and `last_checked: YYYY-MM-DD`. After completing all `###` tasks in a `##` phase, set the phase's `status: done` too.
4. **After each completed phase:** (a) Append a WORKLOG.md entry per `CODING_AGENT_MAIN_WORKFLOW.md` Phase 5 format. (b) Update the `project_firebase_migration.md` memory file (at `~/.claude/projects/.../memory/`) to reflect which phases are done and any key discoveries or blockers.
5. **At session end:** If a phase task is blocked or deferred, add a carry-forward entry to `TODO_WORKFLOW.md` (root of the repo) so the next session resumes cleanly.
6. **Knowledge capture is mandatory:** Tasks 8.4 and 8.5 (KB doc updates + performance feedback) must not be skipped — they are part of the plan, not optional clean-up.

---

## Phase 0 — Key Decisions
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
All decisions below are locked as of 2026-05-05. They are recorded here to prevent re-litigating them mid-execution.

### 0.1 Frontend: Next.js 14 + Firebase App Hosting
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_01
<!-- content -->
SSR with App Router. Server-side proxy route handlers (`/api/chat`, `/api/events/*`, `/api/feedback`, `/api/admin/*`) mint OIDC tokens using `google-auth-library` to call the IAM-only Cloud Run backend. No browser ever holds backend credentials or the Gemini key. This is the canonical Chatbot Template pattern.

### 0.2 Backend: FastAPI on Cloud Run (IAM-only)
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_02
<!-- content -->
Python FastAPI service wrapping the existing `src/core/engine.py`, `src/mcp/`, `src/core/graph_utils.py`, and `src/core/personality.py`. Deployed with `--no-allow-unauthenticated`. Cloud Run spec mirrors Chatbot Template: `minInstances=0`, `maxInstances=2`, `512Mi`, `cpu=1`. Gemini key and Sheets SA JSON stored in Secret Manager. v1 is a blocking POST (no SSE streaming); streaming is a future iteration.

### 0.3 Data Layer: Firestore
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_03
<!-- content -->
All scraped data (`people`, `raw_events`, `research`, `academic_offerings`, `graph`) migrates to Firestore collections. Backend accesses Firestore via Firebase Admin SDK at startup (loads collections into memory), bypassing security rules. No client-side Firestore access. Firestore security rules lock all collections (`allow read, write: if false` for clients).

### 0.4 Scraper: Cloud Run Job + Cloud Scheduler (weekly)
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_04
<!-- content -->
Existing `scripts/update_dataset.py` adapted to write to Firestore instead of local JSON. Packaged as a separate Cloud Run Job (`mcmp-firebase-scraper`), not part of the chat backend image. Triggered weekly (Sunday 03:00 UTC) via Cloud Scheduler. Selenium requirement means the scraper job needs `2Gi` memory. ChromaDB is dropped from the Firebase build.

### 0.5 Auth: Public chat + Google-auth-gated /admin
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_05
<!-- content -->
Chat is fully public (no sign-in required). `/admin` page requires Google sign-in via Firebase Auth. Email allowlist enforced in the Next.js server component — the sole allowed email is `eikasia@eikasia.com`. Admin actions: trigger manual scrape, link to Google Sheets feedback view.

### 0.6 Feedback: Keep Google Sheets
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_06
<!-- content -->
Google Sheets integration kept. FastAPI `/feedback` endpoint handles the `gspread` call using `SHEETS_SA_JSON` from Secret Manager. No change to the existing Sheet ID, schema, or service account access. Migrating to Firestore is a deferred follow-up.

### 0.7 GCP Project: New mcmp-firebase (isolated, org root)
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_07
<!-- content -->
New isolated GCP project `mcmp-firebase` at the **eikasia.com org root** (required by Firebase App Hosting — the CLI picker does not surface projects nested in GCP folders). Existing `mcmp-chatbot` project (owned by `ignacioojea@gmail.com`) and its Streamlit Cloud deployment are untouched. Precedent for the eikasia org: the `chatbot-template-eikasia` project and `eikasia-llc/adk_playground` GitHub org used by the chatbot_template reference implementation.

### 0.8 Repository Layout and Production Branch
- status: done
- type: task
- id: mcmp_firebase_migration.phase_0.task_08
<!-- content -->
```
firebase/
├── frontend/           ← Next.js 14 App Router (Firebase App Hosting)
│   ├── src/app/        ← page components and API route handlers
│   ├── apphosting.yaml
│   └── package.json
├── backend/            ← FastAPI on Cloud Run
│   ├── main.py
│   ├── Dockerfile
│   ├── cloudbuild.yaml
│   ├── deploy-backend.sh
│   └── requirements.txt
├── scraper/            ← Cloud Run Job (weekly scrape)
│   ├── run_scraper.py
│   └── Dockerfile
└── scripts/
    └── migrate_to_firestore.py  ← one-time data migration
```
`app.py`, `src/`, `data/`, `prompts/`, `scripts/`, `tests/` remain completely unchanged.

Production branch: `firebase-branch`. All App Hosting auto-deploys and `deploy-backend.sh` runs source exclusively from this branch.

---

## Phase 1 — Repo & Project Scaffold
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Create the `firebase-branch` production branch and the full `firebase/` folder structure. No GCP resources are created yet. This phase produces a committed scaffold on which all subsequent phases build.

### 1.1 Create firebase-branch from main
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_01
<!-- content -->
```bash
git checkout main && git pull
git checkout -b firebase-branch
git push -u origin firebase-branch
```
This branch is the sole production deploy source. Never merge changes targeting the Firebase deploy back to `main` until the migration is fully validated.

### 1.2 Create firebase/ folder structure
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_02
- blocked_by: [mcmp_firebase_migration.phase_1.task_01]
<!-- content -->
Create `firebase/frontend/`, `firebase/backend/`, `firebase/scraper/`, `firebase/scripts/`. Add `.gitkeep` to each empty directory. Commit on `firebase-branch`.

### 1.3 Backend: Dockerfile and requirements.txt
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_03
- blocked_by: [mcmp_firebase_migration.phase_1.task_02]
<!-- content -->
`firebase/backend/Dockerfile` builds from the **repo root** so it can `COPY src/` and `COPY prompts/`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY firebase/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY firebase/backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

`firebase/backend/requirements.txt`: start from root `requirements.txt`, then:
- **Add**: `fastapi`, `uvicorn[standard]`, `firebase-admin`
- **Remove**: `streamlit`, `chromadb` (not used in Firebase build)
- Pin `google-genai` to the version in use (`google-genai==1.*` or pin exact)

### 1.4 Backend: cloudbuild.yaml and deploy-backend.sh
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_04
- blocked_by: [mcmp_firebase_migration.phase_1.task_03]
<!-- content -->
`firebase/backend/cloudbuild.yaml`: Cloud Build config that runs from the **repo root** (so the Dockerfile can access `src/`). Builds image tagged `backend:<short-sha>` and `backend:latest` in Artifact Registry `us-central1-docker.pkg.dev/mcmp-firebase/mcmp-firebase-app/backend`.

`firebase/backend/deploy-backend.sh`: shell script wrapping `gcloud builds submit`. Hard branch guard — refuses to run unless `git rev-parse --abbrev-ref HEAD` equals `firebase-branch`. Pattern copied verbatim from Chatbot Template `deploy-backend.sh`. After a successful build, the script deploys to Cloud Run with the flags listed in Phase 4.5.

### 1.5 Frontend: Next.js 14 scaffold
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_05
- blocked_by: [mcmp_firebase_migration.phase_1.task_02]
<!-- content -->
From inside `firebase/frontend/`:
```bash
nvm use 20
npx create-next-app@14 . --typescript --tailwind --app --src-dir --import-alias "@/*"
npm install firebase google-auth-library react-markdown
```
Delete the default placeholder page content (`src/app/page.tsx`, `src/app/globals.css` boilerplate). Confirm `npm run dev` starts cleanly at `http://localhost:3000`.

### 1.6 Frontend: apphosting.yaml
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_06
- blocked_by: [mcmp_firebase_migration.phase_1.task_05]
<!-- content -->
`firebase/frontend/apphosting.yaml`:
```yaml
runConfig:
  minInstances: 0
  maxInstances: 2
  memoryMiB: 512
  cpu: 1
  concurrency: 80

env:
  - variable: BACKEND_URL
    secret: BACKEND_URL        # populated in Secret Manager after Phase 4.5
    availability:
      - RUNTIME
  - variable: ALLOWED_ADMIN_EMAILS
    value: "eikasia@eikasia.com"
    availability:
      - RUNTIME
```
`BACKEND_URL` is left as a Secret Manager reference placeholder. After the backend Cloud Run URL is known (Phase 4.5), create the secret and update this file.

### 1.7 Update .gitignore
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_1.task_07
- blocked_by: [mcmp_firebase_migration.phase_1.task_05]
<!-- content -->
Append to root `.gitignore`:
```
# Firebase build
firebase/frontend/.env.local
firebase/frontend/node_modules/
firebase/frontend/.next/
firebase/.firebaserc
```
Keep `firebase/firebase.json` committed (no secrets in it).

---

## Phase 2 — GCP + Firebase Provisioning
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2
- blocked_by: [mcmp_firebase_migration.phase_1]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Create the `mcmp-firebase` GCP project, enable all required APIs, provision IAM service accounts, store secrets in Secret Manager, configure the log sink, initialize Firebase, create the App Hosting backend, and create the Firestore database. These are all one-time console/CLI operations.

**Before starting:**
1. Confirm CLI identity is `eikasia@eikasia.com`: `gcloud config get-value account` must echo `eikasia@eikasia.com`. If not, follow the auth steps in the plan preamble (Operating account section).
2. Capture pre-flight values once authenticated as eikasia:
   - `gcloud organizations list` → copy the eikasia org ID into `<EIKASIA_ORG_ID>` below.
   - `gcloud billing accounts list` → copy the eikasia billing account ID into `<EIKASIA_BILLING_ACCOUNT_ID>` below.
3. Run `nvm use 20 && firebase login --reauth` (as `eikasia@eikasia.com`) on any workstation executing Firebase CLI commands. Node < 20 and stale auth tokens are the two most common failure modes.

### 2.1 Create GCP project mcmp-firebase at org root
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_01
<!-- content -->
Create the project at the **eikasia.com org root** (not inside any folder). Firebase App Hosting's project picker does not surface folder-nested projects. The `--organization` flag pins the project to the eikasia org rather than the executing user's default org.
```bash
gcloud projects create mcmp-firebase \
  --name="MCMP Firebase" \
  --organization=<EIKASIA_ORG_ID>
gcloud billing projects link mcmp-firebase \
  --billing-account=<EIKASIA_BILLING_ACCOUNT_ID>
```
Confirm placement: `gcloud projects describe mcmp-firebase` — `parent.type` must be `organization` and `parent.id` must equal `<EIKASIA_ORG_ID>` (not `folder`, not the default org for any other account).

### 2.2 Enable required APIs
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_02
- blocked_by: [mcmp_firebase_migration.phase_2.task_01]
<!-- content -->
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  logging.googleapis.com \
  firebase.googleapis.com \
  firebasehosting.googleapis.com \
  firebaseapphosting.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  compute.googleapis.com \
  firestore.googleapis.com \
  cloudscheduler.googleapis.com \
  --project=mcmp-firebase
```

### 2.3 Artifact Registry repo
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_03
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
```bash
gcloud artifacts repositories create mcmp-firebase-app \
  --repository-format=docker \
  --location=us-central1 \
  --description="MCMP Firebase Docker images" \
  --project=mcmp-firebase
```
Both the backend and scraper images go in this repo.

### 2.4 Runtime service account mcmp-firebase-app-sa
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_04
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
This SA is used by both the Cloud Run backend service and the Cloud Run scraper job.
```bash
gcloud iam service-accounts create mcmp-firebase-app-sa \
  --project=mcmp-firebase \
  --display-name="MCMP Firebase App Runtime SA"

SA="mcmp-firebase-app-sa@mcmp-firebase.iam.gserviceaccount.com"
for ROLE in \
  roles/secretmanager.secretAccessor \
  roles/logging.logWriter \
  roles/artifactregistry.reader \
  roles/datastore.user; do
  gcloud projects add-iam-policy-binding mcmp-firebase \
    --member="serviceAccount:${SA}" --role="$ROLE"
done
```
`roles/datastore.user` grants Firestore read/write via Admin SDK (Admin SDK uses the runtime SA identity in Cloud Run).

### 2.5 Cloud Build SA roles
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_05
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
```bash
PROJECT_NUM=$(gcloud projects describe mcmp-firebase --format='value(projectNumber)')
BUILD_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"

for ROLE in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/artifactregistry.writer \
  roles/storage.admin \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding mcmp-firebase \
    --member="serviceAccount:${BUILD_SA}" --role="$ROLE"
done
```

### 2.6 Secret Manager: GEMINI_API_KEY and SHEETS_SA_JSON
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_06
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
Values are provided out-of-band. Never stored in the repository.

**Gemini API key — pick one option before running:**
- **(a) Eikasia-owned key (recommended):** Sign in to Google AI Studio as `eikasia@eikasia.com`, create a new API key linked to the `mcmp-firebase` project. Gemini usage bills to eikasia. Clean ownership.
- **(b) Reuse existing key:** Re-use the key already used by the Streamlit deployment (currently linked to the old `mcmp-chatbot` project on `ignacioojea@gmail.com`). Faster, but Gemini charges land on the old account.

```bash
# Gemini API key (option a or b above)
echo -n "AIza..." | gcloud secrets create GEMINI_API_KEY \
  --data-file=- --project=mcmp-firebase

# Google Sheets service account JSON
gcloud secrets create SHEETS_SA_JSON \
  --data-file=/path/to/sheets-sa-key.json \
  --project=mcmp-firebase
```

**Sheets SA — pick one option before running:**
- **(a) New eikasia-owned SA (recommended):** Create a new service account on `mcmp-firebase`, share the existing feedback Sheet (`1N9YOiOQKgjEbA_P0868FQjVjkykhnPrrOnqPxztYSyY`) with the new SA's email (Editor role), download its JSON key, store it as `SHEETS_SA_JSON`. Clean ownership.
- **(b) Reuse existing SA:** Use the existing `mcmp-admin@mcmp-chatbot.iam.gserviceaccount.com` SA JSON. Cross-links the eikasia deploy back to the ignacio-owned SA.

The `SHEETS_SA_JSON` secret holds the complete JSON content of whichever SA you picked. This replaces the `.streamlit/secrets.toml` `[gcp_service_account]` block.

### 2.7 Log sink: WARNING+ exclusion
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_07
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
```bash
gcloud logging sinks update _Default \
  --project=mcmp-firebase \
  --add-exclusion='name=drop-below-warning,filter=severity < WARNING,description=Cost policy: WARNING+ only'
```

### 2.8 Private Google Access on default subnet
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_08
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
```bash
gcloud compute networks subnets update default \
  --region=us-central1 \
  --enable-private-ip-google-access \
  --project=mcmp-firebase
```

### 2.9 Initialize Firebase + create App Hosting backend
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_09
- blocked_by: [mcmp_firebase_migration.phase_2.task_02]
<!-- content -->
```bash
nvm use 20
firebase login --reauth         # must be eikasia@eikasia.com
firebase projects:list          # confirm mcmp-firebase appears under eikasia

cd firebase/frontend
firebase init apphosting
```

**GitHub repo decision (before running `init apphosting`):**
- The mcmp_chatbot repo currently lives under `IgnacioOQ/mcmp_chatbot` (a personal GitHub account separate from `eikasia-llc`).
- App Hosting authorizes via the Firebase GitHub app installed on the org/account hosting the repo. Two options:
  - **(a) Keep repo at `IgnacioOQ/mcmp_chatbot`** — install the Firebase GitHub app on `IgnacioOQ` and grant it access to this repo. Simpler short-term, asymmetric ownership long-term (code on a personal account, infra on eikasia).
  - **(b) Transfer or mirror to `eikasia-llc/mcmp_chatbot`** — matches the `eikasia-llc/adk_playground` pattern used by the chatbot_template. Recommended for consistency with existing eikasia infra.

Wizard answers:

| Prompt | Answer |
|:---|:---|
| Project selection | Use existing → `mcmp-firebase` |
| Backend ID | `mcmp-firebase-app` |
| Region | `us-central1` |
| GitHub repo | `IgnacioOQ/mcmp_chatbot` or `eikasia-llc/mcmp_chatbot` (per decision above) |
| Branch | `firebase-branch` |
| Root directory (relative to repo root) | `firebase/frontend` |

After init, note the auto-created App Hosting runtime SA email (format: `firebase-app-hosting-compute@mcmp-firebase.iam.gserviceaccount.com`). This SA needs `roles/run.invoker` on the Cloud Run backend (granted in Phase 4.6).

### 2.10 Create Firestore database
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_10
- blocked_by: [mcmp_firebase_migration.phase_2.task_09]
<!-- content -->
```bash
# Via Firebase CLI (run from firebase/frontend/ after init)
firebase firestore:databases:create "(default)" \
  --project=mcmp-firebase --location=nam5
```
Or via Firebase Console → Firestore → Create database → Production mode → `nam5` (US multi-region).

### 2.11 Enable Google Auth provider
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_2.task_11
- blocked_by: [mcmp_firebase_migration.phase_2.task_09]
<!-- content -->
Firebase Console (signed in as `eikasia@eikasia.com`) → Authentication → Get started → Google → Enable → set support email to `eikasia@eikasia.com` → Save. Required for the `/admin` page Google sign-in.

---

## Phase 3 — Data Layer (Firestore)
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3
- blocked_by: [mcmp_firebase_migration.phase_2]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Define the Firestore collection schema, write and run the one-time migration from local JSON files to Firestore, update the MCP tools to read from Firestore, and update the scraper to write to Firestore. This phase produces a fully-populated database that the Phase 4 backend can query on startup.

### 3.1 Firestore security rules
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_01
<!-- content -->
Lock all client access. The backend uses Firebase Admin SDK which bypasses these rules entirely.

`firebase/frontend/firestore.rules`:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```
Deploy: `firebase deploy --only firestore:rules --project=mcmp-firebase`.

If a future iteration adds client-side Firestore access (e.g., real-time admin panel), extend the rules then. Do not pre-open them now.

### 3.2 Firestore collections schema
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_02
<!-- content -->
| Collection | Document ID | Source file |
|:---|:---|:---|
| `people` | URL-safe slug of person name (e.g. `hannes-leitgeb`) | `data/people.json` |
| `events` | `{YYYY-MM-DD}_{url-safe-title-slug}` | `data/raw_events.json` |
| `research` | URL-safe slug of topic name | `data/research.json` |
| `academic_offerings` | Program slug (e.g. `bachelor`, `master`, `phd`) | `data/academic_offerings.json` |
| `graph` | Single doc `mcmp_graph` — fields: `content` (raw MD string), `jgraph` (JSON object) | `data/graph/mcmp_graph.md` + `mcmp_jgraph.json` |
| `meta` | Doc `scraping_logs` — field: `data` (raw JSON object) | `data/scraping_logs.json` |

Each document stores all fields from the corresponding JSON entry verbatim. No schema transformation.

### 3.3 Write data migration script
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_03
- blocked_by: [mcmp_firebase_migration.phase_3.task_02]
<!-- content -->
`firebase/scripts/migrate_to_firestore.py`:
- Uses Application Default Credentials (run `gcloud auth application-default login` first while signed in as `eikasia@eikasia.com` — the project owner of `mcmp-firebase`)
- Reads all local `data/*.json` and `data/graph/*` files
- Upserts to Firestore collections per schema in 3.2 using `batch.set()` (500-doc batches)
- Idempotent: safe to re-run without creating duplicates
- Prints progress and doc counts on completion

```bash
gcloud auth application-default login   # sign in as eikasia@eikasia.com
python firebase/scripts/migrate_to_firestore.py --project=mcmp-firebase
```

### 3.4 Update MCP tools to support Firestore backend
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_04
- blocked_by: [mcmp_firebase_migration.phase_3.task_03]
<!-- content -->
Modify `src/mcp/tools.py` (and `src/mcp/server.py` if needed) to respect a `DATA_BACKEND` environment variable:

- **`DATA_BACKEND=json` (default, unchanged):** Tools continue loading from `data/*.json` at module init. The Streamlit build is completely unaffected — this is the zero-risk backward-compatibility path.
- **`DATA_BACKEND=firestore`:** At startup, tools call Firebase Admin SDK to fetch all documents from `people`, `events`, `research`, `academic_offerings`, and `graph` collections into module-level dictionaries (mirroring the current JSON file structure). Total data ~500 KB — the in-memory load takes < 1s and avoids per-query Firestore reads. Tool query logic is unchanged after the load.

The `ChatEngine` init path in `src/core/engine.py` does not need changes — it only calls the MCP tools.

### 3.5 Update scraper for Firestore output
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_05
- blocked_by: [mcmp_firebase_migration.phase_3.task_03]
<!-- content -->
`firebase/scraper/run_scraper.py`:
1. Initialize Firebase Admin SDK (uses runtime SA identity via ADC — no key file needed in Cloud Run)
2. Call `MCMPScraper` (existing logic from `src/scrapers/mcmp_scraper.py`)
3. Run `build_graph.py` (existing logic from `src/utils/build_graph.py`)
4. Upsert all updated data to Firestore using the schema from 3.2
5. Update `meta/scraping_logs` document with run timestamp, counts, and any removed entries

The `academic_offerings` 30-day freshness check reads `meta/scraping_logs` from Firestore (instead of the local file's `mtime`).

The existing `scripts/update_dataset.py` is **not modified** — it continues writing to local JSON for the Streamlit build.

### 3.6 Run migration and verify
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_3.task_06
- blocked_by: [mcmp_firebase_migration.phase_3.task_05]
<!-- content -->
```bash
python firebase/scripts/migrate_to_firestore.py --project=mcmp-firebase
```
Verify in Firebase Console → Firestore:
- `people` collection: expected ~100+ documents
- `events` collection: expected ~hundreds of documents
- `research`, `academic_offerings`, `graph`, `meta` collections present
- Spot-check: open a `people/hannes-leitgeb` document and verify fields match `data/people.json`

---

## Phase 4 — Backend App & First Deploy
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4
- blocked_by: [mcmp_firebase_migration.phase_3]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Create the FastAPI application, deploy it to Cloud Run, and verify it is reachable via IAM token auth. The frontend is not built yet — this phase validates the backend in isolation.

### 4.1 Create firebase/backend/main.py
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_01
<!-- content -->
FastAPI app with the following endpoints:

| Method | Path | Description |
|:---|:---|:---|
| `GET` | `/health` | Returns `{"status": "ok", "data_backend": "firestore"}` |
| `POST` | `/chat` | `{"message": str, "history": [...]}` → `{"response": str, "tool_calls": [{"name": str, "args": {...}}]}` |
| `POST` | `/events/month` | `{"year": int, "month": int}` → `{"event_days": [int, ...]}` (day numbers with events) |
| `GET` | `/events/week` | Returns current-week events list: `[{"title", "speaker", "date", "time", "location", "url"}]` |
| `POST` | `/feedback` | `{"name": str, "message": str}` → appends row to Google Sheet |
| `POST` | `/admin/scrape` | Triggers the scraper Cloud Run Job via `gcloud run jobs execute`; returns `{"status": "started"}` |

`ChatEngine` is initialized at app startup (`@asynccontextmanager lifespan`) with `provider="gemini"`, `use_mcp=True`. The Gemini API key is read from the `GEMINI_API_KEY` environment variable (mounted by Secret Manager). Personality loaded from `prompts/personality.md` (path: `/app/prompts/personality.md` in the container).

v1: `/chat` is a **blocking POST** — full Gemini response returned at once. SSE streaming is a future iteration.

### 4.2 Feedback endpoint: Google Sheets via SHEETS_SA_JSON
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_02
- blocked_by: [mcmp_firebase_migration.phase_4.task_01]
<!-- content -->
`/feedback` reads `SHEETS_SA_JSON` environment variable (mounted from Secret Manager at deploy time). Parses the JSON blob as a service account credentials dict, creates `gspread.Credentials`, and appends a row `[timestamp, name, message]` to the existing sheet (sheet ID from `SHEETS_ID` env var, also in Secret Manager or plain env).

Port the logic directly from `app.py:save_feedback()` — the Sheets sheet ID and service account are unchanged.

Add `SHEETS_ID` to Secret Manager:
```bash
echo -n "1N9YOiOQKgjEbA_P0868FQjVjkykhnPrrOnqPxztYSyY" | \
  gcloud secrets create SHEETS_ID --data-file=- --project=mcmp-firebase
```

### 4.3 Local smoke test
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_03
- blocked_by: [mcmp_firebase_migration.phase_4.task_02]
<!-- content -->
Run with `DATA_BACKEND=json` locally (uses existing `data/*.json` — no Firestore needed for local dev):
```bash
cd firebase/backend
GEMINI_API_KEY=<key> DATA_BACKEND=json uvicorn main:app --reload --port 8080
curl http://localhost:8080/health
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Who is Hannes Leitgeb?","history":[]}'
```
Both commands should return 200 with expected JSON.

### 4.4 First backend deploy via Cloud Build
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_04
- blocked_by: [mcmp_firebase_migration.phase_4.task_03]
<!-- content -->
```bash
git checkout firebase-branch
./firebase/backend/deploy-backend.sh
```
The script enforces the branch guard and submits a Cloud Build job. Cloud Run deploy flags:
- `--no-allow-unauthenticated`
- `--service-account=mcmp-firebase-app-sa@mcmp-firebase.iam.gserviceaccount.com`
- `--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest,SHEETS_SA_JSON=SHEETS_SA_JSON:latest,SHEETS_ID=SHEETS_ID:latest`
- `--set-env-vars=DATA_BACKEND=firestore`
- `--min-instances=0 --max-instances=2 --memory=512Mi --cpu=1`
- `--region=us-central1 --project=mcmp-firebase`

After deploy: note the Cloud Run URL. Add it to Secret Manager as `BACKEND_URL`:
```bash
echo -n "https://mcmp-firebase-backend-<hash>-uc.a.run.app" | \
  gcloud secrets create BACKEND_URL --data-file=- --project=mcmp-firebase
```
Then update `firebase/frontend/apphosting.yaml` `BACKEND_URL` secret reference (already written in Phase 1.6).

### 4.5 Grant App Hosting SA roles/run.invoker
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_05
- blocked_by: [mcmp_firebase_migration.phase_4.task_04]
<!-- content -->
```bash
gcloud run services add-iam-policy-binding mcmp-firebase-backend \
  --region=us-central1 --project=mcmp-firebase \
  --member="serviceAccount:firebase-app-hosting-compute@mcmp-firebase.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```
This is the bridge that allows the Next.js server-side proxy routes to call the IAM-only backend.

### 4.6 Backend smoke test (IAM token)
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_4.task_06
- blocked_by: [mcmp_firebase_migration.phase_4.task_05]
<!-- content -->
```bash
TOKEN=$(gcloud auth print-identity-token)
URL="https://mcmp-firebase-backend-<hash>-uc.a.run.app"

curl -fsS -H "Authorization: Bearer $TOKEN" "$URL/health"
curl -fsS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"smoke test","history":[]}' "$URL/chat"
```
Both must return HTTP 200. If `/chat` returns a Gemini response, the full backend stack (Admin SDK → Firestore → ChatEngine → Gemini) is verified.

---

## Phase 5 — Frontend App & First Deploy
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5
- blocked_by: [mcmp_firebase_migration.phase_4]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Build the Next.js frontend replicating all Streamlit UI features: interactive sidebar calendar with event-day dots and click-to-query, Events This Week list, chat with live MCP tool-call status icons, feedback form, and admin panel. Push to `firebase-branch` to trigger the first App Hosting rollout.

### 5.1 Server-side proxy routes
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_01
<!-- content -->
Create Next.js App Router route handlers (`src/app/api/*/route.ts`) for all backend endpoints. Each handler uses `google-auth-library` to mint an OIDC identity token scoped to `BACKEND_URL`, then forwards the request:

```typescript
// src/app/api/chat/route.ts  (pattern for all proxy routes)
import { GoogleAuth } from 'google-auth-library';
const auth = new GoogleAuth();

export async function POST(req: Request) {
  const body = await req.json();
  const client = await auth.getIdTokenClient(process.env.BACKEND_URL!);
  const res = await client.request({
    url: `${process.env.BACKEND_URL}/chat`,
    method: 'POST',
    data: body,
    responseType: 'json',
  });
  return Response.json(res.data);
}
```

Apply the same pattern to:
- `POST /api/events/month` → backend `/events/month`
- `GET /api/events/week` → backend `/events/week`
- `POST /api/feedback` → backend `/feedback`
- `POST /api/admin/scrape` → backend `/admin/scrape` (protected in 5.6)

### 5.2 Chat UI component
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_02
- blocked_by: [mcmp_firebase_migration.phase_5.task_01]
<!-- content -->
React client component `ChatPanel`:
- Scrollable message list with user/assistant bubbles; auto-scrolls to latest message
- Text input + submit button; Enter to send
- On submit: POST to `/api/chat`; show "Leopold is thinking…" spinner during request
- On response: render assistant message as Markdown (`react-markdown`); show tool-call log below the spinner with icons matching Streamlit (`🔍` search_people, `📚` search_research, `📅` get_events, `🏛️` search_graph, `🔎` grep_data)
- Chat history kept in React state; full history sent to backend with each request

v1: blocking POST. The spinner replaces Streamlit's `st.status` expander. Streaming (SSE) is a future iteration.

### 5.3 Sidebar calendar component
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_03
- blocked_by: [mcmp_firebase_migration.phase_5.task_01]
<!-- content -->
React client component `CalendarWidget`:
- On mount and on month change: fetch event dates from `GET /api/events/month?year=Y&month=M`
- Render 7-column grid (Mon–Sun, Monday first); prev/next month navigation arrows
- Today: distinct background colour (primary accent)
- Event day: small blue dot (●) below the day number
- Click on a day: call a `onDateClick(formattedDate)` prop that injects the prompt `"What talks or events are scheduled for {formattedDate}? Please provide details about each event, including an abstract or description."` into the chat input and auto-submits it

Layout (top to bottom in sidebar): CalendarWidget → feedback form → EventsThisWeek.

### 5.4 Events This Week component
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_04
- blocked_by: [mcmp_firebase_migration.phase_5.task_01]
<!-- content -->
React server component `EventsThisWeek` (or client component with SWR):
- Fetch from `GET /api/events/week` on mount
- For each event: render **speaker name** (bold), [talk title](url) (linked), date/time/location caption
- Show "No events scheduled for this week." when list is empty
- Skip events whose title starts with `[CANCEL` (mirrors Streamlit logic)

### 5.5 Feedback form component
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_05
- blocked_by: [mcmp_firebase_migration.phase_5.task_01]
<!-- content -->
Collapsible React component (collapsed by default, matching Streamlit expander):
- Name field (optional) + message textarea + Submit button
- POST to `/api/feedback`; show success toast on submit, error toast on failure

### 5.6 Admin page (/admin)
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_06
- blocked_by: [mcmp_firebase_migration.phase_5.task_01]
<!-- content -->
`src/app/admin/page.tsx` (Next.js server component with client sub-components for auth):

1. **Auth gate**: client-side Firebase Auth (Google sign-in via `signInWithPopup`/`signInWithRedirect` fallback — see `DEPLOY_FIREBASE_WORKFLOW.md` Step F for the mobile popup-blocked pattern).
2. **Allowlist check**: server component reads the session cookie or client passes the `idToken`; email must be in `ALLOWED_ADMIN_EMAILS` env var. Non-allowed users are redirected to `/`.
3. **Admin UI**:
   - "Trigger Scrape" button → POST `/api/admin/scrape` → show job status
   - Link to the Google Sheets feedback spreadsheet

Firebase SDK init in `src/lib/firebase.ts`:
```typescript
import { initializeApp, getApps } from 'firebase/app';
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FB_API_KEY,
  authDomain: "mcmp-firebase.firebaseapp.com",
  projectId: "mcmp-firebase",
};
export const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
```
Add `NEXT_PUBLIC_FB_API_KEY` to `apphosting.yaml` env (not a secret — Firebase web API keys are public-facing by design).

### 5.7 First App Hosting deploy
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_07
- blocked_by: [mcmp_firebase_migration.phase_5.task_06]
<!-- content -->
```bash
git checkout firebase-branch
# Commit all frontend work
git add firebase/frontend/
git commit -m "feat(firebase): initial Next.js frontend"
git push origin firebase-branch
```
Firebase App Hosting auto-detects the push and triggers a buildpack rollout. Monitor:
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://firebaseapphosting.googleapis.com/v1beta/projects/mcmp-firebase/locations/us-central1/backends/mcmp-firebase-app/rollouts?pageSize=3" \
  | python3 -m json.tool
```
Capture the App Hosting URL from Firebase Console once the rollout completes.

### 5.8 Add App Hosting domain to Firebase Auth authorized domains
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_5.task_08
- blocked_by: [mcmp_firebase_migration.phase_5.task_07]
<!-- content -->
Firebase Console → Authentication → Settings → Authorized domains → Add the App Hosting production URL (format: `mcmp-firebase-app--mcmp-firebase.us-central1.hosted.app`). Required for admin page Google sign-in to work from the production domain.

---

## Phase 6 — Scraper Cloud Run Job
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6
- blocked_by: [mcmp_firebase_migration.phase_3]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Package the MCMP scraper as a Cloud Run Job and schedule it weekly. This phase is independent of Phases 4 and 5 — it can be worked in parallel with the backend and frontend if desired.

### 6.1 Create firebase/scraper/Dockerfile
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_01
<!-- content -->
Selenium requires Chromium, so the scraper image is larger and heavier than the chat backend:
```dockerfile
FROM python:3.11-slim
RUN apt-get update && \
    apt-get install -y chromium chromium-driver && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY firebase/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY scripts/ ./scripts/
COPY firebase/scraper/run_scraper.py .
CMD ["python", "run_scraper.py"]
```
Memory allocation for the Cloud Run Job: `2Gi` (Selenium needs headroom). Timeout: `3600s`.

### 6.2 Create firebase/scraper/run_scraper.py
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_02
- blocked_by: [mcmp_firebase_migration.phase_6.task_01]
<!-- content -->
Orchestration script:
1. Initialize Firebase Admin SDK (ADC — runtime SA identity in Cloud Run; no key file)
2. Instantiate `MCMPScraper` and call `scrape_all()` methods (events, people, research)
3. Check `academic_offerings` freshness from `meta/scraping_logs` in Firestore; only re-scrape if > 30 days
4. Call `build_graph.py` to rebuild the institutional graph from scraped data
5. Upsert all data to Firestore collections using the Phase 3.2 schema (batch writes, 500 docs/batch)
6. Update `meta/scraping_logs` with run timestamp, counts per collection, and any entries absent in current scrape

The existing `scripts/update_dataset.py` is **not modified**.

### 6.3 Create firebase/scraper/cloudbuild.yaml
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_03
- blocked_by: [mcmp_firebase_migration.phase_6.task_02]
<!-- content -->
Similar to `firebase/backend/cloudbuild.yaml` but targets the scraper image. Tags: `scraper:<short-sha>` and `scraper:latest` in the same `mcmp-firebase-app` AR repo.

### 6.4 Deploy Cloud Run Job
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_04
- blocked_by: [mcmp_firebase_migration.phase_6.task_03]
<!-- content -->
Build the scraper image first:
```bash
gcloud builds submit --config firebase/scraper/cloudbuild.yaml . --project=mcmp-firebase
```
Create the Cloud Run Job:
```bash
gcloud run jobs create mcmp-firebase-scraper \
  --image=us-central1-docker.pkg.dev/mcmp-firebase/mcmp-firebase-app/scraper:latest \
  --region=us-central1 --project=mcmp-firebase \
  --service-account=mcmp-firebase-app-sa@mcmp-firebase.iam.gserviceaccount.com \
  --memory=2Gi --cpu=1 \
  --task-timeout=3600s \
  --max-retries=1
```

### 6.5 Create Cloud Scheduler job (weekly)
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_05
- blocked_by: [mcmp_firebase_migration.phase_6.task_04]
<!-- content -->
```bash
gcloud scheduler jobs create http mcmp-firebase-scraper-weekly \
  --location=us-central1 --project=mcmp-firebase \
  --schedule="0 3 * * 0" \
  --uri="https://run.googleapis.com/v2/projects/mcmp-firebase/locations/us-central1/jobs/mcmp-firebase-scraper:run" \
  --message-body="{}" \
  --oauth-service-account-email=mcmp-firebase-app-sa@mcmp-firebase.iam.gserviceaccount.com \
  --time-zone="UTC" \
  --description="Weekly MCMP data scrape — Sunday 03:00 UTC"
```
Grant the runtime SA `roles/run.invoker` on the job if needed (Cloud Scheduler calls the Run API on behalf of the SA).

### 6.6 Manual trigger smoke test
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_6.task_06
- blocked_by: [mcmp_firebase_migration.phase_6.task_05]
<!-- content -->
```bash
gcloud run jobs execute mcmp-firebase-scraper \
  --region=us-central1 --project=mcmp-firebase
```
Monitor via Cloud Logging. After the job completes, spot-check that Firestore `events` collection timestamp on a few docs has been updated. Full scrape can take 20–45 minutes.

---

## Phase 7 — Production Verification Gate
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7
- blocked_by: [mcmp_firebase_migration.phase_5, mcmp_firebase_migration.phase_6]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
End-to-end verification of the full stack. All checks must pass before the Firebase deployment is declared production-ready and the Streamlit deployment is considered a candidate for deprecation.

### 7.1 Chat smoke test
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_01
<!-- content -->
Open the App Hosting URL. Send "Who is Hannes Leitgeb?". Verify: (a) spinner appears, (b) `🔍 search_people` tool icon is shown in the status log, (c) response includes correct research areas and role from Firestore data.

### 7.2 Calendar click → auto-query
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_02
<!-- content -->
Click a day with a blue event dot. Verify: (a) prompt is auto-injected into chat, (b) `📅 get_events` tool icon appears, (c) response lists the correct events for that date.

### 7.3 Events This Week list
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_03
<!-- content -->
Verify Events This Week shows correct events for the current week. Click a talk title link — verify it opens the correct MCMP URL.

### 7.4 Feedback form → Google Sheets
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_04
<!-- content -->
Submit the feedback form with test name and message. Open the Google Sheet (`MCMP Chatbot Feedback`). Verify a new row was appended with the correct timestamp, name, and message.

### 7.5 Admin panel sign-in and scrape trigger
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_05
<!-- content -->
Navigate to `/admin`. Sign in with `eikasia@eikasia.com` (allowed). Verify admin dashboard renders. Click "Trigger Scrape" — verify the Cloud Run Job starts (`gcloud run jobs executions list`). Then test with a non-allowed email (e.g., `ignacioojea@gmail.com`) — verify redirect to `/`.

### 7.6 Cold-start latency
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_06
<!-- content -->
Wait ~5 minutes after last request (allows backend to scale to zero). Send a chat message and measure wall-clock time to first response. If latency exceeds 8 seconds, consider setting `minInstances=1` on the backend (~$8/mo). Document the observed value.

### 7.7 Logging and cost check
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_7.task_07
<!-- content -->
After a chat interaction, verify WARNING+ logs appear:
```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=WARNING' \
  --project=mcmp-firebase --limit=10 \
  --format="table(timestamp,severity,textPayload)"
```
Confirm `minInstances=0` on both the backend service and App Hosting. Check billing console shows $0 for the fresh project at this usage level.

---

## Phase 8 — Documentation, Knowledge Capture & Handover
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8
- blocked_by: [mcmp_firebase_migration.phase_7]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Finalize documentation and project governance files. The Streamlit deployment remains live — no teardown is planned at this stage.

### 8.1 Create firebase/README.md
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8.task_01
<!-- content -->
Document: production App Hosting URL, backend Cloud Run URL, deployment procedures for backend (`deploy-backend.sh`) and frontend (`git push`), local dev setup, scraper job management (`gcloud run jobs execute`), cost levers (`minInstances`), and rollback procedures. Mirror the structure of `INFRASTRUCTURE_CHATBOT_TEMPLATE_SKILL.md`.

### 8.2 Update WORKLOG.md and memory
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8.task_02
<!-- content -->
Append a WORKLOG entry documenting: GCP project ID (`mcmp-firebase`), backend Cloud Run service name, App Hosting backend ID, App Hosting production URL, scraper job name, Cloud Scheduler job name, key architectural decisions (Chatbot Template pattern, Firestore data layer, blocked-POST v1), and any deferred items (SSE streaming, Sheets→Firestore feedback migration).

Also update `project_firebase_migration.md` in the memory folder (`~/.claude/projects/-Users-ignacio-Documents-VS-Code-GitHub-Repositories-mcmp-chatbot/memory/`) to record the final production URLs, service names, and that Phase 0–8 are complete.

### 8.3 Update TODO_WORKFLOW.md
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8.task_03
<!-- content -->
`TODO_WORKFLOW.md` exists at the repo root. Open it and:
1. Delete the `todo.firebase_phase_1` task block (the repo scaffold task — now complete).
2. Confirm `todo.sse_streaming` and `todo.feedback_firestore` blocks are still present; update their `last_checked` dates and `blocked_by` fields now that Phase 7 is done (both are unblocked once the Firebase stack is live).
3. If any new deferred items were identified during Phases 1–7, add them using the Task Template at the bottom of the file.

Do **not** recreate the file or overwrite it — it was bootstrapped during the planning session and contains carry-forward tasks from prior work.

### 8.4 Update KB documents from implementation learnings
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8.task_04
- blocked_by: [mcmp_firebase_migration.phase_8.task_03]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Per `MD_CONVENTIONS.md` Best Practice #11: review whether the three context documents loaded at plan start need updating based on discoveries during MCMP implementation. For each:

1. `mcp__kb_mcp__knowledge_base_read(path="content/reference/INFRASTRUCTURE_CHATBOT_TEMPLATE_REF.md")` — note `content_hash`. Add any corrections or new constraints (e.g., OIDC token scoping edge cases, Artifact Registry naming rules discovered during build).
2. `mcp__kb_mcp__knowledge_base_read(path="content/how-to/INFRASTRUCTURE_CHATBOT_TEMPLATE_SKILL.md")` — note `content_hash`. Add missing runbook steps or pitfalls (e.g., `nvm use 20` requirement for Firebase CLI, `firebase login --reauth` timing).
3. `mcp__kb_mcp__knowledge_base_read(path="content/workflows/DEPLOY_FIREBASE_WORKFLOW.md")` — note `content_hash`. Add any Firebase App Hosting + IAM proxy steps that were missing or incorrect in the KB at plan start.

For each document with changes: present an approval summary (document path + each change as addition or correction with original → replacement text) → wait for explicit user confirmation → `knowledge_base_update`. Skip documents where no new material was discovered.

### 8.5 Record KB performance feedback
- status: todo
- type: task
- id: mcmp_firebase_migration.phase_8.task_05
- blocked_by: [mcmp_firebase_migration.phase_8.task_04]
- owner: agent
- last_checked: 2026-05-05
<!-- content -->
Per `CODING_AGENT_MAIN_WORKFLOW.md` Phase 6: call `knowledge_base_record_performance` once per notable friction or success event from across all implementation sessions (e.g., a missing doc that caused rework, a search that saved significant time). Then call it once with `event_type="session_summary"` listing all kb_mcp tools used in this final session.
