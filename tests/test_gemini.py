"""
Integration tests for ChatEngine with Gemini provider and MCP tools.

These tests make real API calls and require GEMINI_API_KEY to be set.
They are skipped automatically if the key is not available.
"""
import os
import sys
import pytest
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
skip_without_key = pytest.mark.skipif(
    not GEMINI_API_KEY,
    reason="GEMINI_API_KEY not set — skipping live Gemini integration tests",
)


@pytest.fixture(scope="module")
def engine():
    from src.core.engine import ChatEngine
    return ChatEngine(use_mcp=True, provider="gemini")


@skip_without_key
def test_person_research_query(engine):
    """Engine returns a non-empty answer about Ojea's research area."""
    response = engine.generate_response(
        "What does Ignacio Ojea research?", use_mcp_tools=True
    )
    assert response and len(response) > 0


@skip_without_key
def test_person_existence_query(engine):
    """Engine confirms that Ignacio exists in the MCMP database."""
    response = engine.generate_response(
        "Is there someone named Ignacio in the MCMP database?", use_mcp_tools=True
    )
    assert response and len(response) > 0
    assert "ignacio" in response.lower()


@skip_without_key
def test_person_greeting_query(engine):
    """Engine handles a casual greeting + people query."""
    response = engine.generate_response("Hi, who is Ignacio?", use_mcp_tools=True)
    assert response and len(response) > 0


@skip_without_key
def test_person_abbreviated_name_query(engine):
    """Engine resolves an abbreviated last-name-only query."""
    response = engine.generate_response("Who is Ojea?", use_mcp_tools=True)
    assert response and len(response) > 0
    assert "ojea" in response.lower()
