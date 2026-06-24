import pytest
import os
import sys
from src.mcp import tools as mcp_tools
from src.mcp.tools import (
    search_people, search_research, get_events, fuzzy_search, _name_similarity,
)

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_search_people():
    # Test normal search
    results = search_people("Bonatti")
    assert len(results) > 0
    assert "Bonatti" in results[0]['name']
    
    # Test role filter by searching role text explicitly, assuming search_people supports general string matches.
    # Note: `role_filter` argument is no longer supported by search_people.
    results_role = search_people("Doctoral fellow")
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


# ── Fuzzy search ─────────────────────────────────────────────────────────────
# These tests are deliberately data-independent: they monkeypatch load_data with a
# tiny inline fixture, so they pass on any branch regardless of whether data/*.json
# exists (it is gitignored on firebase-branch). They cover the typo-tolerance the
# fuzzy_search tool and the search_people fuzzy fallback add.

_FIXTURE_PEOPLE = [
    {"name": "Tom F. Sterkenburg", "url": "https://example.org/sterkenburg",
     "description": "Philosophy of science and machine learning.",
     "metadata": {"role": "Researcher", "organizational_unit": "MCMP"}},
    {"name": "Hannes Leitgeb", "url": "https://example.org/leitgeb",
     "description": "Logic and philosophy of language.",
     "metadata": {"position": "Chair", "organizational_unit": "MCMP"}},
    {"name": "Stephan Hartmann", "url": "https://example.org/hartmann",
     "description": "Philosophy of physics and Bayesian epistemology.",
     "metadata": {"role": "Chair", "organizational_unit": "MCMP"}},
]


@pytest.fixture
def patch_people(monkeypatch):
    """Make load_data return the inline people fixture (and empty for other files)."""
    monkeypatch.setattr(
        mcp_tools, "load_data",
        lambda filename: _FIXTURE_PEOPLE if filename == "people.json" else [],
    )


def test_name_similarity_typo_vs_unrelated():
    # A surname typo with a dropped middle initial still scores high...
    assert _name_similarity("Tom Sternkenberg", "Tom F. Sterkenburg") >= 0.7
    # ...while unrelated names stay low.
    assert _name_similarity("Tom Smith", "Hannes Leitgeb") < 0.5


def test_fuzzy_search_surfaces_misspelled_person(patch_people):
    results = fuzzy_search("Tom Sternkenberg", database="people")
    assert results, "expected at least one fuzzy match"
    top = results[0]
    assert top["name"] == "Tom F. Sterkenburg"
    assert top["database"] == "people"
    assert top["score"] >= 0.7
    # Ranked by descending score.
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_fuzzy_search_unknown_database_errors():
    out = fuzzy_search("x", database="bogus")
    assert out and "error" in out[0]


def test_fuzzy_search_empty_query_errors():
    out = fuzzy_search("   ")
    assert out and "error" in out[0]


def test_search_people_fuzzy_fallback(patch_people):
    # Exact AND-substring match fails on the typo; the fuzzy fallback kicks in.
    results = search_people("Leitgib")  # typo for "Leitgeb"
    assert results, "expected the fuzzy fallback to surface a candidate"
    assert results[0]["name"] == "Hannes Leitgeb"
    assert results[0].get("approximate") is True
    assert "match_score" in results[0]


def test_search_people_exact_not_flagged_approximate(patch_people):
    # A genuine exact substring match must NOT be tagged approximate.
    results = search_people("Hartmann")
    assert results[0]["name"] == "Stephan Hartmann"
    assert "approximate" not in results[0]


# ── Fuzzy search: events / research / all ────────────────────────────────────

_FIXTURE_EVENTS = [
    {"title": "Talk: Tom F. Sterkenburg (MCMP)", "talk_title": "No Free Lunch and machine learning",
     "url": "https://example.org/ev1",
     "metadata": {"speaker": "Tom F. Sterkenburg", "date": "2026-05-12"}},
    {"title": "Workshop: Modal Logic", "talk_title": "",
     "url": "https://example.org/ev2",
     "metadata": {"speaker": "Hannes Leitgeb", "date": "2026-06-01"}},
]

_FIXTURE_RESEARCH = [
    {"name": "Philosophy of Science", "description": "Confirmation, induction, ML.", "people": []},
    {"name": "Logic and Philosophy of Language", "description": "Modal logic, semantics.", "people": []},
]


@pytest.fixture
def patch_all(monkeypatch):
    """Route each logical dataset to its inline fixture."""
    mapping = {
        "people.json": _FIXTURE_PEOPLE,
        "raw_events.json": _FIXTURE_EVENTS,
        "research.json": _FIXTURE_RESEARCH,
    }
    monkeypatch.setattr(mcp_tools, "load_data", lambda filename: mapping.get(filename, []))


def test_fuzzy_search_events_by_speaker_typo(patch_all):
    # Misspelled speaker name should surface the event via the speaker field.
    results = fuzzy_search("Sternkenberg", database="events")
    assert results, "expected an event match on the misspelled speaker"
    assert results[0]["speaker"] == "Tom F. Sterkenburg"
    assert results[0]["database"] == "events"
    assert results[0]["date"] == "2026-05-12"


def test_fuzzy_search_research_by_area_typo(patch_all):
    results = fuzzy_search("Filosophy of Sience", database="research")
    assert results, "expected a research-area match"
    assert results[0]["name"] == "Philosophy of Science"
    assert results[0]["database"] == "research"


def test_fuzzy_search_all_merges_and_ranks(patch_all):
    results = fuzzy_search("Sterkenburg", database="all", max_results=10)
    dbs = {r["database"] for r in results}
    # Matches the person AND the event (both carry the name), ranked together.
    assert "people" in dbs and "events" in dbs
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_fuzzy_search_respects_max_results(patch_all):
    results = fuzzy_search("Sterkenburg", database="all", max_results=1)
    assert len(results) == 1


def test_fuzzy_search_high_threshold_filters_out(patch_all):
    # A near-impossible threshold should drop every candidate.
    results = fuzzy_search("Sternkenberg", database="people", threshold=0.99)
    assert results == []
