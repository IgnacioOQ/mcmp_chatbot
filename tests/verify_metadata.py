import sys
import os
import json

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.vector_store import VectorStore

def verify_metadata_filtering():
    vs = VectorStore()
    
    # Test 1: Filter by Year (Integer)
    print("\n--- Test 1: Events in 2026 ---")
    results_2026 = vs.query("research seminar", n_results=5, where={"meta_year": 2026})
    print(f"Found {len(results_2026['ids'][0])} results.")
    for meta in results_2026['metadatas'][0]:
        print(f"- {meta.get('title')} (Year: {meta.get('meta_year')})")
        
    # Test 2: Filter by Role (String)
    print("\n--- Test 2: Postdoctoral fellows ---")
    results_postdoc = vs.query("logic", n_results=5, where={"meta_role": "Postdoctoral fellow"})
    print(f"Found {len(results_postdoc['ids'][0])} results.")
    for meta in results_postdoc['metadatas'][0]:
        print(f"- {meta.get('title')} (Role: {meta.get('meta_role')})")

if __name__ == "__main__":
    verify_metadata_filtering()
