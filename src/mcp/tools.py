import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

def load_data(filename: str) -> List[Dict[str, Any]]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def search_people(query: str, role_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for people in the MCMP database.
    
    Args:
        query: Name or keyword to search for in people's profiles.
        role_filter: Optional filter for role (e.g., "chair", "fellow", "student").
    """
    people = load_data("people.json")
    results = []
    
    query = query.lower()
    role_filter = role_filter.lower() if role_filter else None
    
    for person in people:
        name = person.get("name", "").lower()
        desc = person.get("description", "").lower()
        role = person.get("metadata", {}).get("role", "").lower()
        
        # Apply role filter if specified
        if role_filter and role_filter not in role:
            continue
            
        # Apply text query
        if query in name or query in desc:
            results.append({
                "name": person.get("name"),
                "role": person.get("metadata", {}).get("role", "Unknown"),
                "chair": person.get("metadata", {}).get("chair", "Unknown"),
                "url": person.get("url"),
                "research_interests": person.get("metadata", {}).get("research_interests_text", "")[:200] + "..."
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

def get_events(date_range: Optional[str] = None, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get upcoming events.
    
    Args:
        date_range: Optional. "upcoming" (default), "today", "this_week".
        type_filter: Optional type filter (e.g., "talk", "workshop").
    """
    events = load_data("raw_events.json")
    results = []
    
    today = datetime.now()
    
    for event in events:
        title = event.get("title", "")
        meta = event.get("metadata", {})
        date_str = meta.get("date")
        
        # Filter by type
        if type_filter and type_filter.lower() not in title.lower():
            continue
            
        # Filter by date
        if date_str:
            try:
                # Handle YYYY-MM-DD
                evt_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if date_range == "today" and evt_date.date() != today.date():
                    continue
                if date_range == "upcoming" and evt_date < today:
                    continue
                # Simple logic for "this_week" - can be expanded
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
            "location": meta.get("location", "")[:50],
            "speaker": meta.get("speaker"),
            "url": event.get("url")
        })
        
    # Sort by date
    results.sort(key=lambda x: x.get("date", "9999-99-99"))
    return results[:10]
