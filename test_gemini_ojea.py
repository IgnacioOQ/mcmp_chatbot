import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.getcwd())
import logging

logging.basicConfig(level=logging.DEBUG)

from src.core.engine import RAGEngine
engine = RAGEngine(use_mcp=True, provider="gemini")
print("Response:")
try:
    print(engine.generate_response("who is ojea?", use_mcp_tools=True))
except Exception as e:
    print(f"Error: {e}")
