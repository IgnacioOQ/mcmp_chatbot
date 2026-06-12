"""One-time migration: local data/*.json → Firestore (FIREBASE_MIGRATION_PLAN.md §3.2–3.3).

Idempotent (uses batch.set, so re-runs upsert without duplicating). Authenticates
via Application Default Credentials:

    gcloud auth application-default login        # sign in as the mcmp-firebase owner
    python firebase/scripts/migrate_to_firestore.py --project=mcmp-firebase
"""
import argparse
import json
import os
import re
import unicodedata

import firebase_admin
from firebase_admin import firestore

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")


def slug(text: str) -> str:
    """URL-safe lowercase slug; diacritics stripped."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def _read_json(rel_path):
    path = os.path.join(DATA_DIR, rel_path)
    if not os.path.exists(path):
        print(f"  ! missing {rel_path} — skipped")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _commit_in_batches(db, collection, items, id_fn):
    """Upsert items into a collection in 500-doc batches. Returns count written."""
    count = 0
    batch = db.batch()
    pending = 0
    used_ids = {}
    for item in items:
        doc_id = id_fn(item)
        # disambiguate accidental slug collisions
        if doc_id in used_ids:
            used_ids[doc_id] += 1
            doc_id = f"{doc_id}-{used_ids[doc_id]}"
        else:
            used_ids[doc_id] = 0
        batch.set(db.collection(collection).document(doc_id), item)
        pending += 1
        count += 1
        if pending >= 500:
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": args.project})
    db = firestore.client()
    print(f"Migrating local data/ → Firestore project '{args.project}'")

    # people
    people = _read_json("people.json")
    if people is not None:
        n = _commit_in_batches(db, "people", people, lambda p: slug(p.get("name", "unknown")))
        print(f"  people: {n} docs")

    # events  →  {YYYY-MM-DD}_{title-slug}
    events = _read_json("raw_events.json")
    if events is not None:
        def event_id(e):
            date = (e.get("metadata", {}) or {}).get("date", "no-date")
            title = e.get("talk_title") or e.get("title") or "event"
            return f"{date}_{slug(title)}"
        n = _commit_in_batches(db, "events", events, event_id)
        print(f"  events: {n} docs")

    # research
    research = _read_json("research.json")
    if research is not None:
        n = _commit_in_batches(db, "research", research, lambda r: slug(r.get("name", "topic")))
        print(f"  research: {n} docs")

    # academic_offerings
    offerings = _read_json("academic_offerings.json")
    if offerings is not None:
        n = _commit_in_batches(
            db, "academic_offerings", offerings,
            lambda o: slug(o.get("offering_type") or o.get("title") or "offering"),
        )
        print(f"  academic_offerings: {n} docs")

    # graph  →  single doc mcmp_graph {content, jgraph}
    jgraph = _read_json("graph/mcmp_jgraph.json")
    graph_md_path = os.path.join(DATA_DIR, "graph", "mcmp_graph.md")
    graph_md = None
    if os.path.exists(graph_md_path):
        with open(graph_md_path, encoding="utf-8") as f:
            graph_md = f.read()
    if jgraph is not None or graph_md is not None:
        db.collection("graph").document("mcmp_graph").set(
            {"content": graph_md, "jgraph": jgraph}
        )
        print("  graph: 1 doc (mcmp_graph)")

    # meta/scraping_logs  →  {data: <raw json>}
    logs = _read_json("scraping_logs.json")
    if logs is not None:
        db.collection("meta").document("scraping_logs").set({"data": logs})
        print("  meta: 1 doc (scraping_logs)")

    print("Done.")


if __name__ == "__main__":
    main()
