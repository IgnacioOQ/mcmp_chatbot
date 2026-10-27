import asyncio
import importlib.util
import json
import os
import sys
import threading

import pytest
from fastapi.testclient import TestClient

# firebase/backend/main.py is deployed as a top-level module, not a package.
_MAIN = os.path.join(os.path.dirname(__file__), "..", "firebase", "backend", "main.py")
_spec = importlib.util.spec_from_file_location("backend_main", _MAIN)
backend_main = importlib.util.module_from_spec(_spec)
sys.modules["backend_main"] = backend_main
_spec.loader.exec_module(backend_main)


class _Doc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _Collection:
    def __init__(self, store):
        self.store = store

    def add(self, data):
        self.store.append(data)

    def order_by(self, field, direction):
        assert direction == "DESCENDING"
        self._ordered = sorted(self.store, key=lambda d: d[field], reverse=True)
        return self

    def stream(self):
        return [_Doc(d) for d in self._ordered]


class _FakeFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return _Collection(self.collections.setdefault(name, []))


@pytest.fixture
def db(monkeypatch):
    fake = _FakeFirestore()
    monkeypatch.setattr(backend_main, "_get_firestore_client", lambda: fake)
    return fake


@pytest.fixture
def client():
    return TestClient(backend_main.app)


def test_feedback_writes_to_firestore(db, client):
    r = client.post("/feedback", json={"name": "Ada", "message": "Great bot"})
    assert r.json() == {"status": "ok"}
    [doc] = db.collections["feedback"]
    assert doc["name"] == "Ada"
    assert doc["message"] == "Great bot"
    assert doc["timestamp"]


def test_admin_feedback_lists_newest_first(db, client, monkeypatch):
    from firebase_admin import auth
    monkeypatch.setattr(auth, "verify_id_token", lambda t: {"email": "admin@example.com"})
    db.collections["feedback"] = [
        {"timestamp": "2026-01-01T00:00:00", "name": "", "message": "old"},
        {"timestamp": "2026-02-01T00:00:00", "name": "", "message": "new"},
    ]
    r = client.post("/admin/feedback", json={"id_token": "tok"})
    body = r.json()
    assert body["email"] == "admin@example.com"
    assert [f["message"] for f in body["items"]] == ["new", "old"]


def test_admin_feedback_rejects_invalid_token(db, client, monkeypatch):
    from firebase_admin import auth

    def _reject(token):
        raise ValueError("bad token")

    monkeypatch.setattr(auth, "verify_id_token", _reject)
    db.collections["feedback"] = [{"timestamp": "t", "name": "", "message": "secret"}]
    r = client.post("/admin/feedback", json={"id_token": "forged"})
    assert r.status_code == 401
    assert "secret" not in r.text


class _FakeEngine:
    """Runs one tool, then blocks until released before streaming the answer —
    like Gemini, which returns no text until the tool result has been read."""

    def __init__(self):
        self.release = threading.Event()

    def generate_response_stream(self, query, status_callback=None, tool_done_callback=None, **kwargs):
        status_callback("get_events", {"date_range": "upcoming"})
        tool_done_callback("get_events")
        assert self.release.wait(5), "test never released the answer"
        yield "Next talk"
        yield " is Monday."


def _events(lines):
    return [json.loads(line) for line in lines if line]


def test_chat_streams_tool_events_before_answer_is_ready(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr(backend_main, "_get_engine", lambda: engine)
    stream = backend_main.chat(backend_main.ChatRequest(message="next talk?")).body_iterator

    async def read(n):
        return [json.loads(await asyncio.wait_for(stream.__anext__(), 2)) for _ in range(n)]

    async def scenario():
        # Tool events must arrive while the answer is still pending.
        early = await read(2)
        engine.release.set()
        return early, [json.loads(chunk) async for chunk in stream]

    early, rest = asyncio.run(scenario())
    assert early == [
        {"type": "tool_call", "name": "get_events", "args": {"date_range": "upcoming"}},
        {"type": "tool_done", "name": "get_events"},
    ]
    assert rest == [
        {"type": "token", "text": "Next talk"},
        {"type": "token", "text": " is Monday."},
        {"type": "done"},
    ]


def test_chat_reports_engine_failure_as_error_event(monkeypatch, client):
    class _Broken:
        def generate_response_stream(self, *args, **kwargs):
            raise RuntimeError("gemini down")
            yield  # pragma: no cover — makes this a generator

    monkeypatch.setattr(backend_main, "_get_engine", lambda: _Broken())
    resp = client.post("/chat", json={"message": "hi"})
    assert _events(resp.text.splitlines()) == [{"type": "error", "message": "gemini down"}]
