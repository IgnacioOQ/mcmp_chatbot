import importlib.util
import os
import sys

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
