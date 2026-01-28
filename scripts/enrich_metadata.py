import json
import os
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.topic_matcher import TopicMatcher
from src.utils.metadata_extractor import extract_event_metadata, extract_person_metadata, extract_research_metadata


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def enrich_file(filename, extractor_func, label):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"enriching {label} in {filename}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    for item in data:
        description = item.get('description', '')
        # Determine extraction based on label
        if label == 'event':
             new_meta = extractor_func(description)
        elif label == 'person':
            new_meta = extractor_func(description, item.get('title', ''))
        elif label == 'research':
            # Research structure changed to hierarchical
            # We skip flat extraction for top level if it doesnt match expectation
            # But deep projects might need it. For now, skip to avoid breaking new structure
             new_meta = {} 
        else:
            new_meta = {}

        # Merge with existing metadata if any
        if 'metadata' not in item or not isinstance(item['metadata'], dict):
            item['metadata'] = {}
        
        item['metadata'].update(new_meta)
        updated_count += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"Updated {updated_count} items in {filename}.")

def link_people_to_research():
    """
    Links people to research topics based on text analysis.
    Updates both people.json (adding 'research_topics') and research.json (adding 'people').
    """
    people_path = os.path.join(DATA_DIR, 'people.json')
    research_path = os.path.join(DATA_DIR, 'research.json')

    if not os.path.exists(people_path) or not os.path.exists(research_path):
        print("Missing people.json or research.json")
        return

    with open(people_path, 'r', encoding='utf-8') as f:
        people = json.load(f)
    
    with open(research_path, 'r', encoding='utf-8') as f:
        research = json.load(f)

    matcher = TopicMatcher(research)
    
    print("Linking people to research topics...")
    
    # Reset people lists in research to avoid duplicates on re-run
    for topic in research:
        topic['people'] = []
        for proj in topic.get('projects', []):
             proj['people'] = []

    for person in people:
        # Combine distinct sources of text for better matching
        text = person.get('description', '') 
        if 'metadata' in person:
            text += " " + person['metadata'].get('research_interests_text', '')
            text += " " + person['metadata'].get('role', '')
            text += " " + person['metadata'].get('chair', '')
        
        matches = matcher.match_interests(text)
        
        # Update Person
        person['metadata']['research_topics'] = matches
        
        # Update Research Topics
        for m in matches:
            tid = m['topic_id']
            # Find the topic
            topic = next((t for t in research if t['id'] == tid), None)
            if topic:
                person_ref = {"name": person['name'], "url": person['url']}
                if person_ref not in topic['people']:
                    topic['people'].append(person_ref)

    with open(people_path, 'w', encoding='utf-8') as f:
        json.dump(people, f, indent=4, ensure_ascii=False)
        
    with open(research_path, 'w', encoding='utf-8') as f:
        json.dump(research, f, indent=4, ensure_ascii=False)
        
    print(f"Linked research topics for {len(people)} people.")

def main():
    enrich_file('raw_events.json', extract_event_metadata, 'event')
    enrich_file('people.json', extract_person_metadata, 'person')
    # enrich_file('research.json', extract_research_metadata, 'research') # Skip old style
    link_people_to_research()

if __name__ == "__main__":
    main()
