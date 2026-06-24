import json
import os
import re
import threading
import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

# Words that carry no semantic meaning for name/topic searches.
# The LLM sometimes passes the full user utterance as the query (e.g. "a researcher named landes"),
# so we strip these before matching to avoid false negatives.
_STOP_WORDS = {
    "a", "an", "the", "is", "at", "of", "in", "on", "for", "to", "and", "or", "by",
    "named", "called", "researcher", "person", "professor", "faculty", "staff", "member",
    "dr", "prof", "mr", "ms", "mrs", "who", "what", "find", "search", "tell", "me",
    "about", "with", "from", "has", "have", "does", "do", "any", "some", "their",
    "his", "her", "its", "our", "work", "works", "working", "know", "information",
}

def _normalize(text: str) -> str:
    """Lowercase and strip diacritics so 'gonzalez' matches 'González'."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode("ascii")


# Default similarity floor for fuzzy (edit-distance) matching, in [0, 1].
# Tuned so a one- or two-character surname typo clears it (Sternkenberg→Sterkenburg
# scores ~0.85) while unrelated names stay below.
_FUZZY_THRESHOLD = 0.6


def _name_similarity(query: str, candidate: str) -> float:
    """Token-aware edit-distance similarity in [0, 1] between a query and a name.

    Combines the whole-string ratio with a per-query-token best match: each query
    token is scored against its closest candidate token and those are averaged,
    taking the max of that and the full-string ratio. This way 'Tom Sternkenberg'
    still scores high against 'Tom F. Sterkenburg' despite the dropped middle
    initial, while 'Tom Smith' vs 'Tom Jones' stays low. Uses difflib (stdlib,
    Ratcliff-Obershelp) — no external dependency. Diacritics/case are normalised
    first, reusing the same rules as the exact matchers.
    """
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0

    full = SequenceMatcher(None, q, c).ratio()

    # Drop stop words so natural-language noise ("a researcher named ...") doesn't
    # dilute the average; fall back to all tokens if everything was stripped.
    q_tokens = [t for t in q.split() if t not in _STOP_WORDS and len(t) > 1] or q.split()
    c_tokens = c.split() or [c]
    per_token = [
        max(SequenceMatcher(None, qt, ct).ratio() for ct in c_tokens)
        for qt in q_tokens
    ]
    avg = sum(per_token) / len(per_token)
    return max(full, avg)

# Manual cache: only stores files that were successfully loaded.
# lru_cache was replaced because it caches missing-file [] results, causing
# tools to return empty permanently if a dataset didn't exist at first call.
_data_cache: Dict[str, List[Dict[str, Any]]] = {}

# Serialises the first (cold) load of each dataset. FastAPI runs sync endpoints
# in a threadpool, so the parallel sidebar requests (/events/week + /events/month)
# can both miss the cache and stream the whole Firestore collection at once; the
# lock makes the second caller wait and reuse the first one's result.
_data_cache_lock = threading.Lock()

# DATA_BACKEND selects where load_data() reads from:
#   "json"      (default) — local data/*.json files. The Streamlit build is
#                unaffected; this is the zero-risk backward-compatible path.
#   "firestore" — read from Firestore collections (Firebase deploy). See
#                FIREBASE_MIGRATION_PLAN.md §3.4.
DATA_BACKEND = os.environ.get("DATA_BACKEND", "json").lower()

# Firestore collection ↔ local-filename mapping (FIREBASE_MIGRATION_PLAN.md §3.2).
_FIRESTORE_COLLECTIONS = {
    "people.json": "people",
    "research.json": "research",
    "raw_events.json": "events",
    "academic_offerings.json": "academic_offerings",
}

_firestore_client = None


def _get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        import firebase_admin
        from firebase_admin import firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        _firestore_client = firestore.client()
    return _firestore_client


def _load_from_firestore(filename: str):
    """Load one logical dataset from Firestore, mirroring the JSON file shape."""
    db = _get_firestore_client()
    if filename in _FIRESTORE_COLLECTIONS:
        return [doc.to_dict() for doc in db.collection(_FIRESTORE_COLLECTIONS[filename]).stream()]
    if filename == "graph/mcmp_jgraph.json":
        snap = db.collection("graph").document("mcmp_graph").get()
        return snap.to_dict().get("jgraph") if snap.exists else None
    return None


def load_data(filename: str) -> List[Dict[str, Any]]:
    if filename in _data_cache:
        return _data_cache[filename]
    with _data_cache_lock:
        # Re-check inside the lock: another thread may have populated the cache
        # while we were waiting on a concurrent cold load.
        if filename in _data_cache:
            return _data_cache[filename]
        if DATA_BACKEND == "firestore":
            data = _load_from_firestore(filename)
            if data is None:
                return []  # not cached — next call retries Firestore
            _data_cache[filename] = data
        else:
            path = os.path.join(DATA_DIR, filename)
            if not os.path.exists(path):
                return []  # not cached — next call will retry the disk
            with open(path, "r", encoding="utf-8") as f:
                _data_cache[filename] = json.load(f)
    return _data_cache[filename]

def _person_result(person: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a raw people.json record into the search_people result dict.
    Shared by the exact-match path and the fuzzy fallback so the two stay in sync.
    """
    meta = person.get("metadata", {})
    return {
        "name": person.get("name"),
        "role": meta.get("role") or meta.get("position") or "Unknown",
        "chair": meta.get("organizational_unit", "Unknown"),
        "url": person.get("url"),
        "image_url": person.get("image_url"),
        "email": meta.get("email"),
        "phone": meta.get("phone"),
        "room": meta.get("room"),
        "website": meta.get("website"),
        "description": person.get("description", ""),
        "research_interests": meta.get("research_interests_text", ""),
    }


def search_people(query: str) -> List[Dict[str, Any]]:
    """
    Search for people, faculty, and researchers at the MCMP. Use this to find contact info, roles, or research interests of specific individuals.
    ALWAYS use this tool if the user asks about a person and the context is insufficient, even if they only provide a first name.
    
    Args:
        query: Name or keyword to search for in people's profiles (e.g., 'Ignacio', 'Julian Nida-Rumelin', 'Logic').
    """
    people = load_data("people.json")
    results = []
    
    # Normalise and strip stop words so natural-language queries like
    # "a researcher named landes" reduce to ["landes"] before matching,
    # and accent variants like "gonzalez" match "González".
    raw_tokens = _normalize(query).split()
    meaningful_tokens = [t for t in raw_tokens if t not in _STOP_WORDS and len(t) > 1]
    # Fall back to all tokens if everything was stripped (e.g. very short queries)
    search_tokens = meaningful_tokens if meaningful_tokens else raw_tokens

    for person in people:
        name = _normalize(person.get("name", ""))
        desc = _normalize(person.get("description", ""))

        # AND match on name: all tokens must appear (handles "christian list" precisely).
        # Stop-word stripping means natural-language noise is already removed, so AND
        # still works for single-token queries like "landes".
        name_match = all(tok in name for tok in search_tokens)
        # Substring match on description using the full cleaned query
        desc_match = " ".join(search_tokens) in desc

        if name_match or desc_match:
            results.append(_person_result(person))

    if results:
        return results[:10]  # Limit results

    # Exact AND-match found nothing — the name may be misspelled. Fall back to
    # fuzzy (edit-distance) ranking over person names so a typo like
    # "Sternkenberg" still surfaces "Tom F. Sterkenburg". Entries are tagged
    # `approximate` (with the score) so the model can hedge — "Did you mean…?" —
    # rather than presenting a guess as a confirmed hit.
    fuzzy = sorted(
        (
            (_name_similarity(query, person.get("name", "")), person)
            for person in people
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    for score, person in fuzzy[:5]:
        if score < _FUZZY_THRESHOLD:
            break
        results.append({**_person_result(person), "approximate": True, "match_score": round(score, 3)})

    return results

def search_research(topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for research areas and projects.
    
    Args:
        topic: Research topic to filter by (e.g., "Logic", "Philosophy of Science").
    """
    research = load_data("research.json")
    results = []
    
    topic_query = topic.lower() if topic else ""
    
    for area in research:
        area_name = area.get("name", "").lower()
        
        if not topic or topic_query in area_name:
            results.append({
                "area": area.get("name"),
                "description": area.get("description"),
                "people_count": len(area.get("people", [])),
                "subtopics": area.get("subtopics", [])
            })
            
    return results

def get_events(date_range: Optional[str] = None, type_filter: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get upcoming events.

    Each result's `title` is the canonical title to show the user — the actual
    talk title (e.g. "The productive polysemy of scientific language") for
    individual talks, or the listing header (e.g. "Workshop Epsilon Calculus")
    for conferences and workshops. The speaker's name and affiliation are in
    the `speaker` field, so the title never needs to include the speaker.
    `weekday` is the full English weekday name for `date` (e.g. "Wednesday")
    — use it directly rather than computing the day of the week from `date`.

    Args:
        date_range: Optional. "upcoming" (default), "today", "this_week".
        type_filter: Optional type filter (e.g., "talk", "workshop").
        start_date: Optional start date in "YYYY-MM-DD" format.
        end_date: Optional end date in "YYYY-MM-DD" format.
        query: Optional keyword search in title, abstract, or description.
    """
    events = load_data("raw_events.json")
    results = []
    
    today = datetime.now()
    
    # Parse explicit dates if provided
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            pass
            
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Set end date time to end of day if it's just a date, effectively
            # But since we compare dates specifically, we might just compare .date() components
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
            
    query_lower = query.lower() if query else None

    for event in events:
        listing_header = event.get("title", "")
        talk_title = event.get("talk_title", "")
        # Prefer the actual talk title when present; fall back to the listing
        # header (which has the form "Talk: <Speaker> (<Affiliation>)") for
        # events without a single talk title (conferences, workshops).
        display_title = talk_title or listing_header
        meta = event.get("metadata", {})
        date_str = meta.get("date")
        abstract = event.get("abstract", "")
        description = event.get("description", "")

        # Parse the event date once — used for filtering and for the weekday
        # field surfaced to the LLM. Stays None if the date is missing or
        # malformed.
        evt_date = None
        if date_str:
            try:
                evt_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                evt_date = None

        # Filter by content query — search both the listing header and the
        # talk title so queries like "Haueis" still match talks where the
        # speaker name is only in the listing header.
        if query_lower:
            text_content = (listing_header + " " + talk_title + " " + abstract + " " + description).lower()
            if query_lower not in text_content:
                continue

        # Filter by type — type words ("Talk", "Workshop") only ever appear
        # in the listing header, so match against that.
        if type_filter and type_filter.lower() not in listing_header.lower():
            continue

        # Filter by date
        if evt_date is not None:
            # Logic: Explicit dates take precedence over date_range presets
            if start_dt or end_dt:
                if start_dt and evt_date < start_dt:
                    continue
                if end_dt and evt_date > end_dt:
                    continue
            else:
                # Fallback to date_range presets
                if date_range == "today" and evt_date.date() != today.date():
                    continue
                if (date_range == "upcoming" or date_range is None) and evt_date < today:
                    continue
                if date_range == "this_week":
                    delta = (evt_date - today).days
                    if delta < 0 or delta > 7:
                        continue

        weekday = evt_date.strftime("%A") if evt_date is not None else ""

        results.append({
            "title": display_title,
            "date": date_str,
            "weekday": weekday,
            "time": f"{meta.get('time_start')} - {meta.get('time_end')}",
            "location": meta.get("location", ""),
            "speaker": meta.get("speaker"),
            "url": event.get("url"),
            "abstract": abstract,
            "description": description
        })
        
        
    # Sort by date
    results.sort(key=lambda x: x.get("date", "9999-99-99"))
    return results[:10]

def search_graph(query: str) -> List[Dict[str, Any]]:
    """
    Search the institutional graph for relationships between people and organizational units.
    
    Args:
        query: Name of the person or organizational unit to search for.
    """
    graph_data = load_data("graph/mcmp_jgraph.json")
    if not graph_data:
        return []

    # Handle the fact that json.load might return a dict with "nodes" and "edges"
    if isinstance(graph_data, list) and len(graph_data) > 0 and isinstance(graph_data[0], dict) and "nodes" in graph_data[0]:
        graph_dict = graph_data[0]
    elif isinstance(graph_data, dict):
        graph_dict = graph_data
    else:
        return []

    nodes = graph_dict.get("nodes", [])
    edges = graph_dict.get("edges", [])
    
    query_lower = query.lower()
    
    # 1. Find matching nodes
    matching_nodes = []
    for node in nodes:
        if query_lower in node.get("name", "").lower() or query_lower in node.get("id", "").lower():
            matching_nodes.append(node)
            
    if not matching_nodes:
        return []
        
    results = []
    
    # 2. For each matching node, find all connected edges and the corresponding other node
    for target_node in matching_nodes:
        node_id = target_node.get("id")
        
        node_relationships = []
        
        for edge in edges:
            if edge.get("source") == node_id:
                # Find the target node
                related_node = next((n for n in nodes if n.get("id") == edge.get("target")), None)
                if related_node:
                    node_relationships.append({
                        "relationship": edge.get("relationship", "connected_to"),
                        "details": edge.get("properties", ""),
                        "with": related_node.get("name"),
                        "type": related_node.get("type", "Unknown")
                    })
            elif edge.get("target") == node_id:
                # Find the source node
                related_node = next((n for n in nodes if n.get("id") == edge.get("source")), None)
                if related_node:
                    node_relationships.append({
                        "relationship": f"is {edge.get('relationship', 'connected_to')} by",
                        "details": edge.get("properties", ""),
                        "with": related_node.get("name"),
                        "type": related_node.get("type", "Unknown")
                    })
                    
        results.append({
            "entity": target_node.get("name"),
            "type": target_node.get("type"),
            "properties": target_node.get("properties", ""),
            "relationships": node_relationships
        })
        
    return results


# ── Grep helpers ─────────────────────────────────────────────────────────────

_GREP_DB_MAP: Dict[str, Tuple[str, Any]] = {
    "people":             ("people.json",              lambda e: e.get("name",  e.get("url", "?"))),
    "research":           ("research.json",            lambda e: e.get("name",  "?")),
    "events":             ("raw_events.json",          lambda e: e.get("title", "?")),
    "academic_offerings": ("academic_offerings.json",  lambda e: e.get("title", "?")),
}

_SNIPPET_RADIUS = 80  # characters to show either side of the match


def _flatten(obj: Any, prefix: str = ""):
    """Recursively yield (dotted_key, str_value) pairs from a JSON object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                yield (f"{prefix}[{i}]", item)
            else:
                yield from _flatten(item, f"{prefix}[{i}]")
    elif isinstance(obj, str) and obj.strip():
        yield (prefix, obj)


def _match_span(pattern: str, text: str, use_regex: bool) -> Optional[Tuple[int, int]]:
    """Return (start, end) of the first match in text, or None."""
    if use_regex:
        try:
            m = re.search(pattern, text, re.IGNORECASE)
            return (m.start(), m.end()) if m else None
        except re.error:
            # Fall back to literal substring on bad regex
            idx = text.lower().find(pattern.lower())
            return (idx, idx + len(pattern)) if idx != -1 else None
    else:
        idx = text.lower().find(pattern.lower())
        return (idx, idx + len(pattern)) if idx != -1 else None


def _snippet(text: str, span: Tuple[int, int]) -> str:
    """Extract a short context window around the matched span."""
    start, end = span
    lo = max(0, start - _SNIPPET_RADIUS)
    hi = min(len(text), end + _SNIPPET_RADIUS)
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(text) else ""
    excerpt = text[lo:start] + ">>>" + text[start:end] + "<<<" + text[end:hi]
    return prefix + excerpt + suffix


def grep_data(
    pattern: str,
    database: str = "all",
    fields: Optional[List[str]] = None,
    use_regex: bool = False,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """
    Flexible grep-style search across MCMP databases.
    Scans the text content of records and returns compact snippets
    showing exactly where the pattern occurs.

    Use this when the other tools (search_people, get_events, etc.) are too
    narrow — e.g. to find anyone who mentions a specific institution, grant,
    journal, or exact phrase across bios and publications.

    Args:
        pattern:     Keyword or regex pattern to search for.
        database:    Which database to search — "people", "research", "events",
                     or "all" (default).
        fields:      Optional list of field names to restrict the search
                     (e.g. ["description", "metadata.email"]). Searches all
                     string fields when omitted.
        use_regex:   If True, treat pattern as a Python regex (case-insensitive).
                     Defaults to False (plain case-insensitive substring match).
        max_results: Maximum number of matching snippets to return (default 10).
    """
    if not pattern or not pattern.strip():
        return [{"error": "pattern must be a non-empty string"}]

    dbs = (
        list(_GREP_DB_MAP.items())
        if database == "all"
        else [(database, _GREP_DB_MAP[database])] if database in _GREP_DB_MAP
        else []
    )

    if not dbs:
        return [{"error": f"Unknown database '{database}'. Choose from: people, research, events, all."}]

    results: List[Dict[str, Any]] = []
    seen_ids: set = set()  # one snippet per (db, record, field) at most

    for db_name, (filename, id_fn) in dbs:
        for entry in load_data(filename):
            entry_id = id_fn(entry)
            for field_path, value in _flatten(entry):
                # Respect optional field filter
                if fields and not any(f in field_path for f in fields):
                    continue
                # Skip very short values
                if len(value) < 3:
                    continue

                span = _match_span(pattern, value, use_regex)
                if span is None:
                    continue

                key = (db_name, entry_id, field_path)
                if key in seen_ids:
                    continue
                seen_ids.add(key)

                results.append({
                    "database": db_name,
                    "id":       entry_id,
                    "field":    field_path,
                    "snippet":  _snippet(value, span),
                })

                if len(results) >= max_results:
                    return results

    return results


# ── Fuzzy (edit-distance) search ─────────────────────────────────────────────

# Per-database: (filename, fn → the name-like strings to fuzzy-match a query against).
# These are the fields a user is liable to misspell — a person's name, an event's
# speaker or talk title, a research area's name — NOT free-text bios (grep_data
# already covers full-text substring search).
_FUZZY_DB_MAP: Dict[str, Tuple[str, Any]] = {
    "people":   ("people.json",     lambda e: [e.get("name", "")]),
    "research": ("research.json",   lambda e: [e.get("name", "")]),
    "events":   ("raw_events.json", lambda e: [
        (e.get("metadata", {}) or {}).get("speaker", ""),
        e.get("talk_title", ""),
        e.get("title", ""),
    ]),
}


def _fuzzy_result(db_name: str, entry: Dict[str, Any], score: float, matched_on: str) -> Dict[str, Any]:
    """Compact, ranked match. `name`/`matched_on` are the corrected term the model
    should feed into the precise tool next (search_people / get_events / search_research)."""
    meta = entry.get("metadata", {}) or {}
    base = {"database": db_name, "score": round(score, 3), "matched_on": matched_on}
    if db_name == "people":
        base.update({
            "name": entry.get("name"),
            "role": meta.get("role") or meta.get("position") or "Unknown",
            "url": entry.get("url"),
        })
    elif db_name == "events":
        base.update({
            "name": entry.get("talk_title") or entry.get("title"),
            "speaker": meta.get("speaker"),
            "date": meta.get("date"),
            "url": entry.get("url"),
        })
    elif db_name == "research":
        base.update({
            "name": entry.get("name"),
            "description": (entry.get("description") or "")[:200],
        })
    return base


def fuzzy_search(
    query: str,
    database: str = "people",
    max_results: int = 5,
    threshold: float = _FUZZY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Approximate (typo-tolerant) name search across MCMP databases using
    edit-distance matching. Returns the closest-matching names ranked by a
    similarity score in [0, 1], even when the spelling is wrong.

    Use this as a FALLBACK when an exact tool (search_people, get_events,
    search_research) returns nothing and the query is a name that may be
    misspelled — e.g. "Tom Sternkenberg" should surface "Tom F. Sterkenburg".
    Each result's `name`/`matched_on` is the corrected term to feed back into the
    precise tool for full details. Do NOT use this as a first resort or for
    free-text/topic search (use search_people or grep_data for those).

    Args:
        query:       The (possibly misspelled) name to match.
        database:    "people" (default), "events", "research", or "all".
        max_results: Maximum number of ranked matches to return (default 5).
        threshold:   Minimum similarity in [0, 1] to include (default 0.6).
                     Lower it (~0.45) to widen the net on very garbled input.
    """
    if not query or not query.strip():
        return [{"error": "query must be a non-empty string"}]

    if database == "all":
        db_names = list(_FUZZY_DB_MAP.keys())
    elif database in _FUZZY_DB_MAP:
        db_names = [database]
    else:
        return [{"error": f"Unknown database '{database}'. Choose from: people, events, research, all."}]

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for db_name in db_names:
        filename, candidates_fn = _FUZZY_DB_MAP[db_name]
        for entry in load_data(filename):
            best, best_str = 0.0, ""
            for cand in candidates_fn(entry):
                if not cand or not cand.strip():
                    continue
                s = _name_similarity(query, cand)
                if s > best:
                    best, best_str = s, cand
            if best >= threshold:
                scored.append((best, _fuzzy_result(db_name, entry, best, best_str)))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [result for _, result in scored[:max_results]]


def search_academic_offerings(
    query: Optional[str] = None,
    offering_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search academic program info at the MCMP: Master, Bachelor, PhD pathways, and Learning Materials.
    Use for questions about degree programs, application requirements, deadlines, coordinators,
    required documents, contact emails, and study resources.

    Args:
        query: Keyword to search (e.g. "application deadline", "ECTS", "requirements", "PhD").
        offering_type: Optional filter — "master", "bachelor", "phd", "learning_materials".
    """
    offerings = load_data("academic_offerings.json")
    results = []

    query_lower = _normalize(query) if query else ""
    offering_type_lower = offering_type.lower() if offering_type else ""

    for offering in offerings:
        if offering_type_lower and offering_type_lower not in offering.get("offering_type", "").lower():
            continue

        if query_lower:
            searchable = _normalize(
                offering.get("title", "") + " "
                + offering.get("description", "") + " "
                + json.dumps(offering.get("metadata", {}))
            )
            if query_lower not in searchable:
                continue

        metadata = offering.get("metadata", {})
        entry = {
            "program": offering.get("title"),
            "offering_type": offering.get("offering_type"),
            "url": offering.get("url"),
            "description": offering.get("description", "")[:1000],
            "ects": metadata.get("ects"),
            "duration": metadata.get("duration"),
            "language": metadata.get("language"),
            "cost": metadata.get("cost"),
            "application_deadline": metadata.get("application_deadline"),
            "application_opens": metadata.get("application_opens"),
            "coordinators": metadata.get("coordinators"),
            "contact_email": metadata.get("contact_email"),
            "contact_emails": metadata.get("contact_emails"),
            "required_documents": metadata.get("required_documents"),
            "admission_requirements": metadata.get("admission_requirements"),
            "open_to": metadata.get("open_to"),
            "external_resources": metadata.get("external_resources"),
        }
        # Strip None values — Gemini's function calling may discard results containing None
        results.append({k: v for k, v in entry.items() if v is not None})

    return results[:10]


# ---------------------------------------------------------------------------
# Tool: ask_clarification
# ---------------------------------------------------------------------------
def ask_clarification(question: str) -> dict:
    """
    Surface a clarification question to the user before executing a search.

    Call this tool when the user's request is ambiguous — for example, when
    a name could refer to multiple people, a topic spans multiple unrelated
    research areas, or the intent of the question is unclear.

    The tool is a transparent pass-through: it returns the question directly
    so the UI can display it as a chat message, giving the user a chance to
    refine their query before any data fetching occurs.

    Args:
        question: A clear, concise question for the user that explains what
                  information is needed. Example:
                  "Do you mean the logician Hannes Leitgeb, or the physicist
                   Hans Leitgeb? Could you give me a bit more context?"

    Returns:
        dict with 'clarification_needed' (the question text) and
        'status': 'waiting_for_user' so callers can detect this special case.
    """
    return {
        "clarification_needed": question,
        "status": "waiting_for_user",
    }
