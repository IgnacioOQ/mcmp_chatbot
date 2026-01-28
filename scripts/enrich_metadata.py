import json
import os
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
            new_meta = extractor_func(description)
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

def main():
    enrich_file('raw_events.json', extract_event_metadata, 'event')
    enrich_file('people.json', extract_person_metadata, 'person')
    enrich_file('research.json', extract_research_metadata, 'research')

if __name__ == "__main__":
    main()
