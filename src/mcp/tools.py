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
        # Look for 'role' or 'position' (scraper uses 'position')
        role = person.get("metadata", {}).get("role", "")
        if not role:
             role = person.get("metadata", {}).get("position", "")
        role = role.lower()
        
        # Apply role filter if specified
        if role_filter and role_filter not in role:
            continue
            
        # Apply text query
        if query in name or query in desc:
            display_role = person.get("metadata", {}).get("role") or person.get("metadata", {}).get("position") or "Unknown"

            results.append({
                "name": person.get("name"),
                "role": display_role,
                "chair": person.get("metadata", {}).get("chair", "Unknown"),
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
