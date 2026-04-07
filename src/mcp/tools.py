import json
import os
import re
import unicodedata
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

# Manual cache: only stores files that were successfully loaded.
# lru_cache was replaced because it caches missing-file [] results, causing
# tools to return empty permanently if a dataset didn't exist at first call.
_data_cache: Dict[str, List[Dict[str, Any]]] = {}

def load_data(filename: str) -> List[Dict[str, Any]]:
    if filename not in _data_cache:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            return []  # not cached — next call will retry the disk
        with open(path, "r", encoding="utf-8") as f:
            _data_cache[filename] = json.load(f)
    return _data_cache[filename]

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
            display_role = person.get("metadata", {}).get("role") or person.get("metadata", {}).get("position") or "Unknown"

            results.append({
                "name": person.get("name"),
                "role": display_role,
                "chair": person.get("metadata", {}).get("organizational_unit", "Unknown"),
                "url": person.get("url"),
                "image_url": person.get("image_url"),
                "email": person.get("metadata", {}).get("email"),
                "phone": person.get("metadata", {}).get("phone"),
                "room": person.get("metadata", {}).get("room"),
                "website": person.get("metadata", {}).get("website"),
                "description": person.get("description", ""),
                "research_interests": person.get("metadata", {}).get("research_interests_text", "")
            })
            
    return results[:10] # Limit results

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
        title = event.get("title", "")
        meta = event.get("metadata", {})
        date_str = meta.get("date")
        abstract = event.get("abstract", "")
        description = event.get("description", "")
        
        # Filter by content query
        if query_lower:
            text_content = (title + " " + abstract + " " + description).lower()
            if query_lower not in text_content:
                continue
        
        # Filter by type
        if type_filter and type_filter.lower() not in title.lower():
            continue
            
        # Filter by date
        if date_str:
            try:
                # Handle YYYY-MM-DD
                evt_date = datetime.strptime(date_str, "%Y-%m-%d")
                
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
                        
            except ValueError:
                pass # skip date check if format unknown
        
        results.append({
            "title": title,
            "date": date_str,
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

    from src.utils.logger import log_info as _log
    import os as _os
    _expected_path = _os.path.join(DATA_DIR, "academic_offerings.json")
    _log(f"[search_academic_offerings] query={query!r} offering_type={offering_type!r} offerings_loaded={len(offerings)} path_exists={_os.path.exists(_expected_path)} path={_expected_path}")

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
