import os
from dotenv import load_dotenv
import google.generativeai as genai

print(f"1. Before load_dotenv: {os.getenv('GEMINI_API_KEY')}")

load_dotenv(override=True) # Force reload to be sure what's in the file
file_key = os.getenv('GEMINI_API_KEY')
print(f"2. After load_dotenv (override=True): {file_key}")

if not file_key:
    print("No key found!")
    exit(1)

print("3. Testing key with list_models...")
try:
    genai.configure(api_key=file_key)
    # Just list execution to verify auth
    models = list(genai.list_models())
    print(f"Success! Found {len(models)} models.")
except Exception as e:
    print(f"Error: {e}")
