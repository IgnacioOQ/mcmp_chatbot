import os
import json
import glob

def parse_markdown_file(filepath):
    """
    Parses a markdown file to extract title, content, and metadata.
    Assumes MD_CONVENTIONS.md style: Headers are ignored for now, just taking the whole content 
    or basic splitting. For RAG definition, we want the whole text.
    """
    filename = os.path.basename(filepath)
    title = filename.replace(".md", "").replace("_", " ").title()
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple heuristic: remove metadata block if present (between --- or after headers)
    # For now, we'll just take the whole content but try to strip the initial metadata lines if they exist
    # and look for the <!-- content --> separator which is standard in this project.
    
    clean_content = content
    if "<!-- content -->" in content:
        # Take everything after the first content separator
        clean_content = content.split("<!-- content -->", 1)[1].strip()
        
    return {
        "title": title,
        "url": f"file:///data/{filename}", # Virtual URL for local knowledge
        "description": clean_content,
        "scraped_at": "2024-01-01T00:00:00", # Placeholder or current time
        "type": "knowledge"
    }

def update_knowledge_json():
    knowledge_dir = "data"
    output_file = "data/knowledge.json"
    
    knowledge_items = []
    
    # Specific file we care about right now, but could be specific folder
    target_files = ["data/WHAT_IS_RAG.md"]
    
    for filepath in target_files:
        if os.path.exists(filepath):
            item = parse_markdown_file(filepath)
            knowledge_items.append(item)
            print(f"Processed {filepath}")
        else:
            print(f"Warning: {filepath} not found.")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(knowledge_items, f, indent=4, ensure_ascii=False)
    
    print(f"Saved {len(knowledge_items)} items to {output_file}")

if __name__ == "__main__":
    update_knowledge_json()
