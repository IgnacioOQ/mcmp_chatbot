"""MCMP Firebase backend — FastAPI wrapper around the existing ChatEngine.

Deployed to Cloud Run (IAM-only). All data access goes through the MCP tools,
which read from Firestore when DATA_BACKEND=firestore. The Gemini key and the
Google Sheets service account are mounted from Secret Manager as env vars.

v1: /chat is a blocking POST (no SSE streaming) — see FIREBASE_MIGRATION_PLAN.md §4.1.
"""
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from pydantic import BaseModel

from src.core.engine import ChatEngine, DEFAULT_GEMINI_MODEL
from src.mcp.tools import load_data

DATA_BACKEND = os.environ.get("DATA_BACKEND", "json")

_engine: ChatEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the engine once at startup. GEMINI_API_KEY is read from the env
    # (mounted from Secret Manager). With DATA_BACKEND=firestore the MCP tools
    # lazily load each collection from Firestore on first use.
    global _engine
    _engine = ChatEngine(provider="gemini", use_mcp=True)
    yield


app = FastAPI(title="MCMP Firebase Backend", lifespan=lifespan)


# ── Schemas ──────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list = []


class MonthRequest(BaseModel):
    year: int
    month: int


class FeedbackRequest(BaseModel):
    name: str = ""
    message: str


# ── Endpoints ──────────────────────────────────────────────────────────────--
@app.get("/health")
def health():
    return {"status": "ok", "data_backend": DATA_BACKEND}


@app.post("/chat")
def chat(req: ChatRequest):
    """Blocking chat turn. Returns the answer plus the tool calls that ran."""
    tool_calls: list[dict] = []

    def _callback(tool_name, args):
        tool_calls.append({"name": tool_name, "args": args or {}})

    response = _engine.generate_response(
        req.message,
        use_mcp_tools=True,
        model_name=DEFAULT_GEMINI_MODEL,
        chat_history=req.history,
        status_callback=_callback,
    )
    return {"response": response, "tool_calls": tool_calls}


@app.post("/events/month")
def events_month(req: MonthRequest):
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
        if d.year != req.year or d.month != req.month:
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
