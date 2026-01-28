import re
from datetime import datetime
from typing import Dict, Any, Optional

def extract_event_metadata(description: str) -> Dict[str, Any]:
    """
    Extracts metadata from an event description.
    
    Fields extracted:
    - date (ISO format if possible)
    - time_start
    - time_end
    - location
    - speaker
    """
    metadata = {}
    
    # Clean up description
    desc_clean = description.replace('\n', ' ').strip()
    
    # Extract Date - Look for patterns like "28 January 2026" or "Date: ... 28 January 2026"
    # This is a bit heuristic based on the provided samples.
    date_match = re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', desc_clean, re.IGNORECASE)
    if date_match:
        try:
            date_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
            date_obj = datetime.strptime(date_str, "%d %B %Y")
            metadata['date'] = date_obj.strftime("%Y-%m-%d")
            metadata['year'] = date_obj.year
            metadata['month'] = date_obj.strftime("%B")
        except ValueError:
            pass

    # Extract Time
    # Pattern: 10:00 am - 12:00 pm
    time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm)?)\s*-\s*(\d{1,2}:\d{2}\s*(?:am|pm)?)', desc_clean, re.IGNORECASE)
    if time_match:
        metadata['time_start'] = time_match.group(1)
        metadata['time_end'] = time_match.group(2)
    else:
        # Single time pattern
        single_time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm))', desc_clean, re.IGNORECASE)
        if single_time_match:
            metadata['time_start'] = single_time_match.group(1)

    # Extract Location
    # Pattern: Location: ... (until end of line or specific delimiters)
    loc_match = re.search(r'Location:\s*(.*?)(?:Title:|Abstract:|$)', description, re.DOTALL | re.IGNORECASE)
    if loc_match:
        metadata['location'] = loc_match.group(1).replace('\n', ' ').strip()

    # Extract Speaker
    # Pattern: Speakers ... or implicit
    speaker_match = re.search(r'Speakers?\s*(.*?)(?:Please note|$)', description, re.DOTALL | re.IGNORECASE)
    if speaker_match:
        speaker_text = speaker_match.group(1).replace('\n', ' ').strip()
        # Clean up some noise if present
        metadata['speaker'] = speaker_text

    return metadata


def extract_person_metadata(description: str, title: str = "") -> Dict[str, Any]:
    """
    Extracts metadata from a person's description.
    
    Fields extracted:
    - role
    - chair
    - research_interests (keywords)
    """
    metadata = {}
    
    desc_clean = description.replace('\n', ' ')
    
    # Extract Role
    roles = [
        "Professor", "Assistant Professor", "Postdoctoral fellow", "Postdoctoral researcher", 
        "Doctoral fellow", "Visiting fellow", "Visiting researcher", "Lecturer",
        "Akademischer Rat", "Akademische RÃ¤tin", "Teaching Fellow" # Handle special chars if needed
    ]
    
    for role in roles:
        if role.lower() in desc_clean.lower():
            metadata['role'] = role
            break
            
    # Extract Chair / Affiliation
    # Pattern: Chair of ... MCMP
    chair_match = re.search(r'(Chair of [^,.]+)', desc_clean)
    if chair_match:
        metadata['chair'] = chair_match.group(1).strip()
    elif "MCMP" in desc_clean:
        metadata['chair'] = "MCMP" # Default if loose affiliation found
        
    return metadata


def extract_research_metadata(description: str) -> Dict[str, Any]:
    """
    Extracts metadata from a research project description.
    
    Fields extracted:
    - funded_by
    - duration
    - leader
    - chair
    """
    metadata = {}
    
    # Funded by
    funding_match = re.search(r'Funded by:\s*(.*?)(?:Project duration|People|$)', description, re.DOTALL | re.IGNORECASE)
    if funding_match:
        metadata['funded_by'] = funding_match.group(1).replace('\n', ' ').strip()

    # Duration
    # Pattern: (2023 - 2029) or Project duration: 2023 - 2026
    duration_match = re.search(r'Project duration:\s*(.*?)(?:People|Chair|$)', description, re.DOTALL | re.IGNORECASE)
    if duration_match:
        metadata['duration'] = duration_match.group(1).replace('\n', ' ').strip()
        
    # People / Leader
    people_match = re.search(r'People:\s*(.*?)(?:Chair|$)', description, re.DOTALL | re.IGNORECASE)
    if people_match:
        metadata['team'] = people_match.group(1).replace('\n', ' ').strip()
        if "Project leader" in metadata['team']:
            # Try to isolate leader name
            leader_match = re.search(r'([^\(]+)\(Project leader\)', metadata['team'])
            if leader_match:
                metadata['leader'] = leader_match.group(1).strip()

    # Chair
    chair_match = re.search(r'Chair:\s*(.*?)(?:Project page|$)', description, re.DOTALL | re.IGNORECASE)
    if chair_match:
        metadata['chair'] = chair_match.group(1).replace('\n', ' ').strip()

    return metadata

if __name__ == "__main__":
    # Simple test
    test_event_desc = """
    28 Jan
    Research Seminar in Decision and Action Theory
    Date: Wed: 10:00 am - 12:00 pm 28 January 2026
    Location: Ludwigstr. 31 Ground floor, room 021
    Speakers Sophie Kikkert
    """
    print("Event Extract:", extract_event_metadata(test_event_desc))
    
    test_person_desc = "Dr. Conrad Friedrich Postdoctoral fellow MCMP Office address: Ludwigstr. 31"
    print("Person Extract:", extract_person_metadata(test_person_desc))
    
    test_research_desc = "Funded by: DFG Project duration: 2023 - 2026 People: Dr. Tom Sterkenburg (Project leader) Chair: Chair of Philosophy of Science"
    print("Research Extract:", extract_research_metadata(test_research_desc))
