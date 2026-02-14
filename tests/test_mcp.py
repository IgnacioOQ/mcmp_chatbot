import pytest
import os
import sys
from src.mcp.tools import search_people, search_research, get_events

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_search_people():
    # Test normal search
    results = search_people("Bonatti")
    assert len(results) > 0
    assert "Bonatti" in results[0]['name']
    
    # Test role filter
    results_role = search_people("Bonatti", role_filter="Doctoral fellow")
    assert len(results_role) > 0
    
    # Test unknown
    results_empty = search_people("XylophoneUnicornSearch")
    assert len(results_empty) == 0

def test_search_research():
    # Test empty returns all top level
    results = search_research()
    assert len(results) > 0
    
    # Test specific topic
    results_logic = search_research("Logic")
    assert len(results_logic) > 0
    assert any("Logic" in r['area'] for r in results_logic)

def test_get_events():
    # Since date depends on "today", we check structure mainly
    results = get_events(date_range="upcoming")
    assert isinstance(results, list)
    
    if len(results) > 0:
        assert 'title' in results[0]
        assert 'date' in results[0]

def test_search_graph():
    from src.mcp.tools import search_graph
    
    # Test with a known entity (should find something in the graph)
    result = search_graph("Logic")
    assert isinstance(result, str)
    assert len(result) > 0
    
    # Test with unknown entity
    result_empty = search_graph("XylophoneUnicornSearch")
    assert "No institutional relationships found" in result_empty
