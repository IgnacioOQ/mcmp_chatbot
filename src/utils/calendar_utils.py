from datetime import datetime

def prepare_calendar_events(raw_events):
    """
    Converts raw events from data/raw_events.json into FullCalendar format.
    https://fullcalendar.io/docs/event-object
    """
    calendar_events = []
    
    for event in raw_events:
        # Basic fields
        title = event.get("title", "Event")
        url = event.get("url", "#")
        
        # Metadata extraction
        metadata = event.get("metadata", {})
        date_str = metadata.get("date") # e.g., "2026-01-28"
        time_start = metadata.get("time_start") # e.g., "10:00 am" or "10:00"
        time_end = metadata.get("time_end")     # e.g., "12:00 pm"
        
        if not date_str:
            # Skip events without a date
            continue
            
        # Format start/end for FullCalendar (ISO 8601)
        # We need to combine date and time.
        # If time is missing, it's an all-day event.
        
        start_iso = date_str
        end_iso = None
        all_day = True
        
        if time_start:
            # Try to parse time and combine
            try:
                # Normalize time format: "10:00 am" -> "10:00 AM" for parsing
                # or handle "10:00"
                # Simple heuristic parser or use dateutil if available (not in requirements yet)
                # Let's try basic strptime
                
                # Check for am/pm
                time_fmt = "%H:%M"
                if "am" in time_start.lower() or "pm" in time_start.lower():
                    time_fmt = "%I:%M %p"
                    
                # Clean string
                clean_start = time_start.replace(".", "").upper() # 10.00 am -> 1000 AM? No.
                # Just upper for AM/PM
                clean_start = time_start.upper().replace(".", "")
                
                dt_start = datetime.strptime(f"{date_str} {clean_start}", f"%Y-%m-%d {time_fmt}")
                start_iso = dt_start.isoformat()
                all_day = False
                
                if time_end:
                    clean_end = time_end.upper().replace(".", "")
                    dt_end = datetime.strptime(f"{date_str} {clean_end}", f"%Y-%m-%d {time_fmt}")
                    end_iso = dt_end.isoformat()
                    
            except Exception as e:
                # If parsing fails, fall back to date-only
                pass

        cal_event = {
            "title": title,
            "start": start_iso,
            "url": url, # Optional: linking to the event page
            # Custom props for tooltip/modal
            "extendedProps": {
                "description": event.get("description", "")[:200] + "...",
                "location": metadata.get("location", "TBD"),
                "speaker": metadata.get("speaker", "")
            } 
        }
        
        if end_iso:
            cal_event["end"] = end_iso
            
        calendar_events.append(cal_event)
        
    return calendar_events
