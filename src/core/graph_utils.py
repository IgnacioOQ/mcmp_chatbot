
import re
import json
from typing import Optional, List, Dict
from pathlib import Path
from collections import defaultdict

class GraphUtils:
    def __init__(self, graph_path: str = "data/graph/mcmp_graph.md"):
        self.graph_path = Path(graph_path)
        self.nodes = []
        self.edges = []
        self.adj_list = defaultdict(list)
        self._load_graph()

    def _load_graph(self):
        """Loads and parses the markdown graph file."""
        if not self.graph_path.exists():
            return

        with open(self.graph_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.nodes = self._parse_table(content, "Nodes")
        self.edges = self._parse_table(content, "Edges")
        self._build_adjacency_list()

    def _build_adjacency_list(self):
        """Builds an adjacency list for O(1) neighbor lookup."""
        self.adj_list.clear()
        for edge in self.edges:
            source = edge.get('source')
            target = edge.get('target')
            if source and target:
                self.adj_list[source].append(target)
                self.adj_list[target].append(source)

    def _parse_table(self, content: str, section_name: str) -> List[Dict]:
        """Parses a markdown table from a specific section."""
        # Regex to find the table under the section header
        # Matches: ### SectionName followed by a table structure
        pattern = fr"###\s*{section_name}\s*\n\|([^\n]+)\|\s*\n\|[-:|\s]+\|\s*\n((?:\|[^\n]+\|\s*\n?)+)"
        match = re.search(pattern, content)
        
        if not match:
            return []

        header_row = match.group(1).strip()
        headers = [h.strip().lower() for h in header_row.split('|') if h.strip()]
        
        data_rows = match.group(2).strip().split('\n')
        parsed_data = []

        for row in data_rows:
            cells = [c.strip() for c in row.split('|') if c.strip() or c == '']
            # Handle potential empty first/last cells due to | start/end
            if row.strip().startswith('|'):
                cells = cells[1:] # Drop first empty if | exists
            if row.strip().endswith('|'):
                cells = cells[:-1] # Drop last empty if | exists
            
            # Simple zip mapping, handles partial rows gracefully
            row_dict = {}
            for i, h in enumerate(headers):
                if i < len(cells):
                    row_dict[h] = cells[i]
                else:
                    row_dict[h] = ""
            parsed_data.append(row_dict)
            
        return parsed_data

    def get_subgraph(self, query: str, max_depth: int = 1) -> Dict:
        """
        Extracts a subgraph relevant to the query.
        Finds nodes matching keywords in the query, then expands to neighbors.
        """
        query_lower = query.lower()
        relevant_nodes = set()
        
        # 1. Find directly matching nodes (by ID, Name, or Type)
        for node in self.nodes:
            searchable_text = f"{node.get('id', '')} {node.get('name', '')} {node.get('type', '')}".lower()
            if any(term in searchable_text for term in query_lower.split()):
                relevant_nodes.add(node.get('id'))

        if unused := True: # Expand to neighbors
            current_layer = list(relevant_nodes)
            for _ in range(max_depth):
                next_layer = set()
                for node_id in current_layer:
                    # Find edges connected to this node
                    if node_id in self.adj_list:
                        next_layer.update(self.adj_list[node_id])
                
                # Add found neighbors to relevant set
                relevant_nodes.update(next_layer)
                current_layer = list(next_layer)

        # Filter nodes and edges
        subgraph_nodes = [n for n in self.nodes if n.get('id') in relevant_nodes]
        subgraph_edges = [
            e for e in self.edges 
            if e.get('source') in relevant_nodes and e.get('target') in relevant_nodes
        ]
        
        return {"nodes": subgraph_nodes, "edges": subgraph_edges}

    def to_natural_language(self, subgraph: Dict) -> str:
        """Converts a subgraph into a natural language description string."""
        if not subgraph['nodes']:
            return ""

        lines = []
        
        # Helper to get node name
        node_map = {n['id']: n.get('name', n['id']) for n in subgraph['nodes']}
        node_type_map = {n['id']: n.get('type', '') for n in subgraph['nodes']}
        
        # Describe entities
        lines.append("Institutional Context:")
        for node in subgraph['nodes']:
            name = node.get('name')
            ntype = node.get('type')
            props = node.get('properties', '')
            desc = f"- **{name}** ({ntype})"
            if props:
                desc += f": {props}"
            lines.append(desc)
            
        if subgraph['edges']:
            lines.append("\nRelationships:")
            for edge in subgraph['edges']:
                source_name = node_map.get(edge.get('source'), edge.get('source'))
                target_name = node_map.get(edge.get('target'), edge.get('target'))
                rel = edge.get('relationship', 'related to')
                props = edge.get('properties', '')
                
                desc = f"- {source_name} **{rel}** {target_name}"
                if props:
                    desc += f" ({props})"
                lines.append(desc)
                
        return "\n".join(lines)
