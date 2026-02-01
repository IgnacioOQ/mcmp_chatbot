
import sys
import os
import json
from src.core.engine import RAGEngine
from src.mcp.tools import search_people, get_events

# Add src to path just in case
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_rag_retrieval():
    print("--- Testing RAG Retrieval (Vector Store) ---")
    try:
        engine = RAGEngine(provider="dummy", api_key="dummy") # We don't need real API key for retrieval test
    except ValueError:
        # If it fails due to missing key, we might need to mock it or just set a dummy env var
        os.environ["OPENAI_API_KEY"] = "dummy"
        engine = RAGEngine(provider="openai", api_key="dummy", use_mcp=False)

    query = "Anne Deng"
    print(f"Querying for: {query}")
    
    # We use the internal method to see what chunks are retrieved
    chunks = engine.retrieve_with_decomposition(query)
    
    print(f"Found {len(chunks)} chunks.")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"Text Content:\n{chunk['text']}")
        print(f"Metadata Keys: {list(chunk['metadata'].keys())}")
        # Check if description is in metadata
        if 'meta_description' in chunk['metadata']:
             print(f"Metadata Description: {chunk['metadata']['meta_description'][:100]}...")
        else:
             print("Metadata Description: NOT FOUND")

def test_mcp_tools():
    print("\n--- Testing MCP Tools ---")
    
    print("Searching for 'Anne Deng'...")
    people = search_people("Anne Deng")
    print(json.dumps(people, indent=2))
    
    print("\nGet Upcoming Events...")
    events = get_events(date_range="upcoming")
    if events:
        print(json.dumps(events[0], indent=2))
    else:
        print("No upcoming events found.")

if __name__ == "__main__":
    test_rag_retrieval()
    test_mcp_tools()
