import os
import sys
import toml
from src.core.engine import RAGEngine

# Add src to path just in case
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def verify():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
            if api_key:
                print("Loaded API key from .streamlit/secrets.toml")
        except Exception as e:
            print(f"Failed to load secrets: {e}")

    if not api_key:
        print("GEMINI_API_KEY not found. Skipping live verification.")
        return

    print("Initializing RAGEngine with MCP...")
    # Pass api_key explicitly
    engine = RAGEngine(provider="gemini", api_key=api_key, use_mcp=True)
    
    query = "List all upcoming events at the MCMP."
    print(f"Query: {query}")
    
    response = engine.generate_response(query, use_mcp_tools=True)
    print("\nResponse:")
    print(response)

if __name__ == "__main__":
    verify()
