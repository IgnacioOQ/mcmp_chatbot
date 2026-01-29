import os
import sys
import toml
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

def list_models():
    """
    Lists all available Gemini models for the provided API key.
    Checks environment variables and Streamlit secrets for the key.
    """
    # 1. Try Environment Variable
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 2. Try Streamlit Secrets
    if not api_key:
        try:
            secrets_path = os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml')
            if os.path.exists(secrets_path):
                secrets = toml.load(secrets_path)
                api_key = secrets.get("GEMINI_API_KEY")
                if api_key:
                    print(f"Loaded API key from {secrets_path}")
        except Exception as e:
            print(f"Failed to load secrets: {e}")

    if not api_key:
        print("Error: GEMINI_API_KEY not found in env or .streamlit/secrets.toml")
        return

    print(f"Using API Key: {api_key[:5]}...{api_key[-4:]}")

    try:
        client = genai.Client(api_key=api_key)
        print("\nListing available models...")
        
        # list() returns a pager, we iterate it
        # Filtering for models that support 'generateContent' could be done, 
        # but listing all shows the full capabilities.
        for model in client.models.list():
            print(f"- {model.name}")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
