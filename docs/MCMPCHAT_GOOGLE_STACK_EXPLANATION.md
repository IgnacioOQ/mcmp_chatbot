# How the MCMP Chatbot Works — Firebase, Google Cloud & Google AI Studio

- status: active
- type: explanation
- description: Short explanation of how the MCMP Chatbot runs and how it uses Firebase, Google Cloud, and Google AI Studio.

<!-- content -->

The MCMP Chatbot is a question-answering app for the **Munich Center for Mathematical Philosophy**. A visitor asks about events, people, research, or degree programs; an LLM answers using structured tools backed by scraped MCMP data. The whole thing runs on Google's platform, split across three services that each own one job:

- **Firebase** — hosts and serves the app, handles sign-in, and stores the data.
- **Google Cloud** — runs the backend that does the actual work, behind IAM.
- **Google AI Studio** — the source of the Gemini API key that powers the LLM.

## The request flow

```
Browser
  └─ Next.js frontend (Firebase App Hosting)
        └─ /api/* proxy route mints an OIDC token
              └─ FastAPI backend (Cloud Run, IAM-only)
                    ├─ ChatEngine → Google Gemini API   (answers)
                    └─ MCP tools → Firestore             (data)
```

1. The browser loads the **Next.js** chat UI.
2. When you send a message, it hits a server-side route under `firebase/frontend/src/app/api/*`. That route runs *on the server*, not in the browser.
3. The route mints a short-lived **OIDC identity token** (`firebase/frontend/src/lib/backend.ts`) and calls the backend. The browser never sees backend credentials or the Gemini key.
4. The **FastAPI backend** (`firebase/backend/main.py`) wraps the shared Python core. For chat it calls **Gemini**; the model decides which **MCP tools** to call; those tools read **Firestore**.
5. The answer (plus the tool calls that ran) returns up the chain to the browser.

The calendar widget and "Events This Week" sidebar use the same path (`/events/month`, `/events/week`), but those endpoints skip the LLM and just read event data directly.

## Firebase — hosting, auth, and data

Firebase is the user-facing layer. The project is `mcmp-firebase`.

- **App Hosting** serves the Next.js 14 frontend. Pushing to the `firebase-branch` git branch triggers an automatic build and rollout — no manual deploy step for the frontend. Runtime config lives in `firebase/frontend/apphosting.yaml`.
- **Authentication** gates the `/admin` page with Google sign-in against an email allowlist. The public chat needs no login. The Firebase web API key (`NEXT_PUBLIC_FB_API_KEY`) ships in the client bundle — Firebase web keys are public by design, not secrets.
- **Firestore** is the live datastore. The MCP tools load the `people`, `events`, `research`, `academic_offerings`, `graph`, and `meta` collections via the Firebase Admin SDK (which bypasses security rules; direct client access is locked off). A weekly scheduled routine re-scrapes the MCMP site and upserts fresh data into Firestore, so the answers stay current.

> Firebase App Hosting is itself built on top of Google Cloud (it runs the Next.js server on a managed Cloud Run instance), so the line between "Firebase" and "Google Cloud" below is about *how you manage each piece*, not separate machines.

## Google Cloud — the backend and the plumbing

Google Cloud runs the parts that should never be exposed to the browser.

- **Cloud Run** hosts the FastAPI backend (`mcmp-firebase-backend`, region `us-central1`). It is **IAM-only**: the only thing allowed to call it is the frontend's server, using the OIDC token described above. There is no public URL you can curl without credentials.
- **Secret Manager** holds the real secrets — the Gemini API key, the Google Sheets service-account JSON, and the Sheet ID — and mounts them into the backend as environment variables at runtime.
- **Cloud Build** builds the backend container image from the repo (`firebase/backend/Dockerfile`) during deploy (`deploy-backend.sh`).
- A **service account** (`mcmp-firebase-app-sa@mcmp-firebase`) gives the running backend its identity for reading Firestore.
- A **Google Sheet** receives user feedback, written by the `/feedback` endpoint via a service account.

In short: Firebase is the front door; Cloud Run + Secret Manager + Firestore are the locked back office.

## Google AI Studio — the Gemini key

Google AI Studio (`aistudio.google.com`) is where the **Gemini API key** comes from. It is not a runtime dependency — the app never calls AI Studio directly. Its only role is issuing the key:

- You generate the key in AI Studio.
- For production, the key lives in **Secret Manager** as `GEMINI_API_KEY` and is mounted into the Cloud Run backend.
- For local development, you export it as an env var when running the backend.

At runtime the `ChatEngine` (`src/core/engine.py`) uses that key to call the **Gemini API**, which is the model that reads your question, decides which MCP tools to call, and writes the final answer.

## Putting it together

| Concern | Service | Where |
|:---|:---|:---|
| Serve the web UI | Firebase App Hosting | `firebase/frontend/` |
| Sign-in (admin) | Firebase Authentication | `/admin` + allowlist |
| Store the data | Firebase / Firestore | `people`, `events`, … collections |
| Run the LLM backend | Google Cloud Run (IAM-only) | `firebase/backend/main.py` |
| Hold secrets | Google Secret Manager | `GEMINI_API_KEY`, `SHEETS_SA_JSON`, `SHEETS_ID` |
| Build the backend image | Google Cloud Build | `firebase/backend/Dockerfile` |
| Power the answers | Gemini API (key from Google AI Studio) | `src/core/engine.py` |

For deeper detail see the project [README](../README.md), the deploy workflow in [MCMPCHAT_FIREBASE_DEPLOY_WORKFLOW.md](MCMPCHAT_FIREBASE_DEPLOY_WORKFLOW.md), and the scraping reference in [MCMP_SCRAPING_REF.md](MCMP_SCRAPING_REF.md).
