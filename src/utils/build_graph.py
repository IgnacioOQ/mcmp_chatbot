import json
import re
import os
from pathlib import Path

def clean_text(text):
    if not text:
        return ""
    # Basic cleaning
    return text.replace("\n", " ").replace("\t", " ").strip()

def normalize_id(name):
    # Create a simple ID from name: "Hannes Leitgeb" -> "hannes_leitgeb"
    # Remove titles
    name = re.sub(r'(Prof\.|Dr\.|DDr\.|PD|M\.A\.|M\.Sc\.|M\.Phil\.|B\.A\.|M\.Mus\.)', '', name)
    # Remove parens
    name = re.sub(r'\(.*?\)', '', name)
    name = name.strip().lower().replace(" ", "_")
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name

def extract_role(description):
    description = description.lower()
    if "chair" in description and "co-director" in description:
        return "Chair & Co-Director"
    if "chair" in description and "director" not in description and "secretary" not in description and "fellow" not in description:
        # Check if they are THE chair (Prof.)
        if "prof." in description or "professor" in description:
             pass # heuristic, might be Assistant Prof.
    
    roles = [
        "co-director",
        "chair",
        "assistant professor",
        "postdoctoral researcher",
        "postdoctoral fellow",
        "doctoral fellow",
        "doctoral student",
        "teaching fellow",
        "visiting fellow",
        "visiting researcher",
        "research fellow",
        "secretary",
        "administration",
        "student assistant",
        "emeritus"
    ]
    
    for r in roles:
        if r in description:
            return r.title()
    return "Member"

def extract_chair(description):
    # Heuristic to find chair affiliation
    chairs = [
        "Chair of Philosophy of Science",
        "Chair of Logic and Philosophy of Language",
        "Chair of Philosophy and Decision Theory",
        "Chair of Theoretical Philosophy",
        "Chair of Philosophy and Political Theory"
    ]
    
    found_chairs = []
    for chair in chairs:
        if chair.lower() in description.lower():
            found_chairs.append(chair)
    
    return found_chairs

def run():
    base_dir = Path(os.getcwd())
    people_file = base_dir / "data/people.json"
    
    if not people_file.exists():
        # Try to find data dir relative to this file if cwd is wrong
        base_dir = Path(__file__).parent.parent.parent
        people_file = base_dir / "data/people.json"
        
    if not people_file.exists():
        print(f"File not found: {people_file}")
        return

    with open(people_file, 'r', encoding='utf-8') as f:
        people = json.load(f)

    nodes = []
    edges = []
    
    # 1. Add Chair Nodes
    chairs = [
        "Chair of Philosophy of Science",
        "Chair of Logic and Philosophy of Language",
        "Chair of Philosophy and Decision Theory",
        "Chair of Theoretical Philosophy",
        "Chair of Philosophy and Political Theory"
    ]
    
    chair_ids = {}
    for c in chairs:
        cid = c.lower().replace(" ", "_").replace("__", "_")
        chair_ids[c] = cid
        nodes.append({
            "id": cid,
            "name": c,
            "type": "Organizational Unit",
            "properties": "MCMP Chair"
        })

    # 2. Add People Nodes and Edges
    person_id_map = {} # Name -> ID

    for p in people:
        raw_name = p['name']
        pid = normalize_id(raw_name)
        person_id_map[raw_name] = pid
        
        description = p.get('description', '')
        role = extract_role(description)
        
        # Add Node
        nodes.append({
            "id": pid,
            "name": clean_text(raw_name),
            "type": "Person",
            "properties": f"Role: {role}"
        })
        
        # Add Chair Edges
        p_chairs = extract_chair(description)
        for c in p_chairs:
            cid = chair_ids[c]
            edges.append({
                "source": pid,
                "target": cid,
                "relationship": "affiliated_with",
                "properties": role
            })
            
            # If they are The Chair (Role=Chair), also add 'leads' edge
            if role == "Chair" or role == "Chair & Co-Director":
                 edges.append({
                    "source": pid,
                    "target": cid,
                    "relationship": "leads",
                    "properties": "Head of Chair"
                })

    # 3. Add Supervision Edges (Second Pass to better matching)
    for p in people:
        description = p.get('description', '')
        pid = normalize_id(p['name'])
        
        # Pattern: "supervision of [Names]"
        # This is tricky because names vary. 
        # We will iterate over all known people and check if their name appears after "supervision of"
        
        lower_desc = description.lower()
        if "supervision of" in lower_desc or "supervised by" in lower_desc:
            # Find which known person is supervisors
            for supervisor_name, supervisor_id in person_id_map.items():
                # Split supervisor name to get last name or full name
                # "Hannes Leitgeb" -> check "Leitgeb" if unqiue? No, check full parts.
                
                # Check for "Hannes Leitgeb" or "Prof. Leitgeb"
                # Simplify: Check if supervisor_id parts appear in window after "supervision"
                
                # Simple check: is the supervisors full name in the description?
                # Excluding self
                if supervisor_id != pid:
                    # check "First Last" in description
                    # Normalize name for check
                    sn_parts = supervisor_name.split()
                    
                    # Heuristics: Check "Hannes Leitgeb", "Stephan Hartmann"
                    # people.json names include titles: "Prof. DDr. Hannes Leitgeb"
                    # We normalized them in keys.
                    
                    # Matches "Hannes Leitgeb" in "supervision of Prof. DDr. Hannes Leitgeb"
                    
                    # Create a cleaner name for search: "Hannes Leitgeb" from "Prof. DDr. Hannes Leitgeb"
                    clean_s_name = re.sub(r'(Prof\.|Dr\.|DDr\.|PD|M\.A\.|M\.Sc\.)', '', supervisor_name).strip()
                    
                    if clean_s_name in description:
                         edges.append({
                            "source": pid,
                            "target": supervisor_id,
                            "relationship": "supervised_by",
                            "properties": "PhD/Research Supervision"
                        })
                    

    # 4. Generate Output
    
    # MD content
    md_lines = [
        "# MCMP Institutional Graph",
        "- status: active",
        "- type: context",
        "- context_dependencies: {'utils': 'src/core/graph_utils.py'}",
        "<!-- content -->",
        "",
        "### Nodes",
        "| id | name | type | properties |",
        "|---|---|---|---|",
    ]
    
    # Deduplicate nodes
    seen_nodes = set()
    for n in nodes:
        if n['id'] not in seen_nodes:
            md_lines.append(f"| {n['id']} | {n['name']} | {n['type']} | {n['properties']} |")
            seen_nodes.add(n['id'])
            
    md_lines.append("")
    md_lines.append("### Edges")
    md_lines.append("| source | target | relationship | properties |")
    md_lines.append("|---|---|---|---|")
    
    for e in edges:
        md_lines.append(f"| {e['source']} | {e['target']} | {e['relationship']} | {e['properties']} |")
        
    md_path = base_dir / "data/graph/mcmp_graph.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    print(f"Graph MD written to {md_path}")
    
    # JSON Output
    json_path = base_dir / "data/graph/mcmp_jgraph.json"
    graph_json = {
        "nodes": [n for n in nodes if n['id'] in seen_nodes], # reuse deduped
        "edges": edges
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(graph_json, f, indent=4)
        
    print(f"Graph JSON written to {json_path}")

if __name__ == "__main__":
    run()
