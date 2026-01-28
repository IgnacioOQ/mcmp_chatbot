
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.graph_utils import GraphUtils

def test_graph_retrieval():
    print("Testing GraphUtils...")
    gu = GraphUtils()
    
    print(f"Loaded {len(gu.nodes)} nodes and {len(gu.edges)} edges.")
    assert len(gu.nodes) > 0, "No nodes loaded"
    assert len(gu.edges) > 0, "No edges loaded"

    # Test retrieval for "Leitgeb"
    query = "Who is Hannes Leitgeb?"
    print(f"\nQuery: {query}")
    subgraph = gu.get_subgraph(query)
    text = gu.to_natural_language(subgraph)
    print("Result:")
    print(text)
    
    assert "Hannes Leitgeb" in text
    assert "Chair of Logic" in text
    assert "leads" in text

    # Test retrieval for "Philosophy of Science"
    query = "Tell me about the Chair of Philosophy of Science"
    print(f"\nQuery: {query}")
    subgraph = gu.get_subgraph(query)
    text = gu.to_natural_language(subgraph)
    print("Result:")
    print(text)
    
    assert "Chair of Philosophy of Science" in text
    assert "Stephan Hartmann" in text

    print("\nSUCCESS: All graph tests passed!")

if __name__ == "__main__":
    test_graph_retrieval()
