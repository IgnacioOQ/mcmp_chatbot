"""MCMP Firebase backend — FastAPI wrapper around the existing ChatEngine.

Deployed to Cloud Run (IAM-only). All data access goes through the MCP tools,
which read from Firestore when DATA_BACKEND=firestore. The Gemini key and the
Google Sheets service account are mounted from Secret Manager as env vars.

v1: /chat is a blocking POST (no SSE streaming) — see FIREBASE_MIGRATION_PLAN.md §4.1.
"""
import json
import os
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.engine import ChatEngine, DEFAULT_GEMINI_MODEL
from src.mcp.tools import load_data

DATA_BACKEND = os.environ.get("DATA_BACKEND", "json")

_engine: ChatEngine | None = None


def _get_engine() -> ChatEngine:
    """Build the Gemini ChatEngine lazily — on the first /chat call, not at
    startup. The calendar endpoints (/events/*) never touch the engine, so this
    keeps the heavyweight MCPServer / personality / Gemini-client init off the
    sidebar's cold-start critical path. GEMINI_API_KEY is read from the env
    (mounted from Secret Manager); with DATA_BACKEND=firestore the MCP tools
    lazily load each collection from Firestore on first use.
    """
    global _engine
    if _engine is None:
        _engine = ChatEngine(provider="gemini", use_mcp=True)
    return _engine


app = FastAPI(title="MCMP Firebase Backend")


# ── Schemas ──────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []


class FeedbackRequest(BaseModel):
    name: str = ""
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────────--
@app.get("/health")
def health():
    return {"status": "ok", "data_backend": DATA_BACKEND}


@app.post("/chat")
def chat(req: ChatRequest):
    """Streaming chat turn (NDJSON).

    Emits one event per line as the turn unfolds so the UI can show progress in
    real time instead of waiting for the whole answer:
      {"type": "tool_call", "name": ..., "args": ...}  — each time a tool fires
      {"type": "token", "text": ...}                   — answer chunks as they stream
      {"type": "done"}                                 — turn complete
      {"type": "error", "message": ...}                — failure mid-turn

    The instrumented tools fire `status_callback` synchronously while the model
    runs them (before the answer text streams), so draining the pending tool
    events before each token keeps the wire order matching execution order.
    """
    engine = _get_engine()

    def event_stream():
        pending: list[dict] = []

        def _callback(tool_name, args):
            pending.append({"type": "tool_call", "name": tool_name, "args": args or {}})

        def _drain():
            while pending:
                yield json.dumps(pending.pop(0)) + "\n"

        try:
            for chunk in engine.generate_response_stream(
                req.message,
                use_mcp_tools=True,
                model_name=DEFAULT_GEMINI_MODEL,
                chat_history=req.history,
                status_callback=_callback,
            ):
                yield from _drain()
                if chunk:
                    yield json.dumps({"type": "token", "text": chunk}) + "\n"
            yield from _drain()
            yield json.dumps({"type": "done"}) + "\n"
        except Exception as e:  # noqa: BLE001 — surface any turn failure to the client
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        # Discourage proxy/CDN buffering so events flush as they are produced.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/events/month")
def events_month(year: int, month: int):
    """Events in the given month, plus the day numbers that have at least one.

    `event_days` powers the calendar dots; `events` powers the inline day-click
    preview (speaker / location / description). Speaker/title resolution mirrors
    /events/week and the Streamlit sidebar.
    """
    days = set()
    events = []
    for event in load_data("raw_events.json"):
        outer_title = event.get("title", "")
        if outer_title.upper().startswith("[CANCEL"):
            continue
        meta = event.get("metadata", {})
        date_str = meta.get("date")
        if not date_str:
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d.year != year or d.month != month:
            continue
        days.add(d.day)

        speaker = meta.get("speaker")
        title = event.get("talk_title") or outer_title or "Untitled"
        if (not speaker or speaker == "Unknown Speaker") and "Talk" in outer_title and ":" in outer_title:
            parts = outer_title.split(":", 1)
            if len(parts) > 1:
                speaker = parts[1].strip()

        # Truncate with an ellipsis only when the description actually overflows,
        # so empty descriptions don't render as a bare "..." (ports the
        # calendar_utils.prepare_calendar_events fix from commit 2036672).
        raw_description = event.get("description", "") or ""
        description = raw_description[:200] + "..." if len(raw_description) > 200 else raw_description

        events.append({
            "day": d.day,
            "title": title,
            "speaker": speaker or "",
            "location": meta.get("location"),
            "description": description,
            "url": event.get("url", "#"),
        })
    events.sort(key=lambda e: e["day"])
    return {"event_days": sorted(days), "events": events}


@app.get("/events/week")
def events_week():
    """Events for the current week (Mon–Sun). Ports the Streamlit sidebar logic."""
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    out = []
    for event in load_data("raw_events.json"):
        outer_title = event.get("title", "")
        if outer_title.upper().startswith("[CANCEL"):
            continue
        meta = event.get("metadata", {})
        date_str = meta.get("date")
        if not date_str:
            continue
        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (start_of_week <= event_date <= end_of_week):
            continue

        speaker = meta.get("speaker")
        title = event.get("talk_title") or outer_title or "Untitled"
        if (not speaker or speaker == "Unknown Speaker") and "Talk" in outer_title and ":" in outer_title:
            parts = outer_title.split(":", 1)
            if len(parts) > 1:
                speaker = parts[1].strip()
        if not speaker:
            speaker = "Unknown Speaker"

        out.append({
            "title": title,
            "speaker": speaker,
            "date": event_date.isoformat(),
            "time": meta.get("time_start", "Time TBA"),
            "location": meta.get("location"),
            "url": event.get("url", "#"),
        })
    out.sort(key=lambda x: x["date"])
    return out


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    """Append a feedback row to the existing Google Sheet (ports app.save_feedback)."""
    import gspread
    from google.oauth2.service_account import Credentials

    sa_info = json.loads(os.environ["SHEETS_SA_JSON"])
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(sa_info, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["SHEETS_ID"]).sheet1
    sheet.append_row([datetime.now().isoformat(), req.name, req.message])
    return {"status": "ok"}


@app.post("/admin/scrape")
def admin_scrape():
    """Trigger the scraper Cloud Run Job (created in Phase 6) via the Run Admin API."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    project = os.environ.get("GCP_PROJECT", "mcmp-firebase")
    region = os.environ.get("GCP_REGION", "us-central1")
    job = os.environ.get("SCRAPER_JOB", "mcmp-firebase-scraper")
    url = (f"https://run.googleapis.com/v2/projects/{project}/locations/{region}"
           f"/jobs/{job}:run")
    creds, _ = google.auth.default()
    resp = AuthorizedSession(creds).post(url)
    return {"status": "started" if resp.ok else "error", "code": resp.status_code}
