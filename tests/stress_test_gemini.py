"""
Stress test for the Gemini MCP integration.

Runs a battery of representative queries, captures which MCP tools fire,
measures latency, and checks per-query expectations. Prints a summary
report at the end.

Run:  python -m tests.stress_test_gemini
"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.engine import ChatEngine, DEFAULT_GEMINI_MODEL  # noqa: E402

if not os.environ.get("GEMINI_API_KEY"):
    print("GEMINI_API_KEY not set — aborting.")
    sys.exit(1)


# Each case: (label, query, expected_tools_subset, must_contain_lower)
# - expected_tools_subset: tool names that SHOULD fire (subset, not exact set)
# - must_contain_lower: substrings that should appear in the response (lower-cased compare)
CASES = [
    (
        "person_full_name",
        "Tell me about Hannes Leitgeb.",
        {"search_people"},
        ["leitgeb"],
    ),
    (
        "person_partial_name",
        "Who is Ojea?",
        {"search_people"},
        ["ojea"],
    ),
    (
        "person_topic_lookup",
        "Who works on Bayesianism at the MCMP?",
        {"search_people"},  # may also call search_research / grep_data as fallback
        [],
    ),
    (
        "research_area",
        "What subtopics exist under Logic at the MCMP?",
        {"search_research"},
        ["logic"],
    ),
    (
        "events_upcoming",
        "What talks are coming up?",
        {"get_events"},
        [],
    ),
    (
        "events_date_range",
        "What events are scheduled between 2026-05-01 and 2026-06-30?",
        {"get_events"},
        [],
    ),
    (
        "graph_org_question",
        "Who leads the Chair of Logic and Philosophy of Language?",
        {"search_graph"},  # may also call search_people
        [],
    ),
    (
        "academic_offerings_master",
        "How do I apply for the Master in Logic and Philosophy of Science?",
        {"search_academic_offerings"},
        [],
    ),
    (
        "academic_offerings_phd",
        "What are the PhD application contacts at the MCMP?",
        {"search_academic_offerings"},
        [],
    ),
    (
        "fallback_obscure_topic",
        "Does anyone at the MCMP work on quantum gravity?",
        set(),  # no specific tool required, but at least one MUST fire
        [],
    ),
    (
        "multi_tool_person_plus_events",
        "What does Hannes Leitgeb research and what are his upcoming events?",
        {"search_people", "get_events"},
        ["leitgeb"],
    ),
    (
        "ambiguous_or_missing",
        "Who is Smith at the MCMP?",
        set(),  # at least one tool should fire (search_people probably empty → fallback)
        [],
    ),
    (
        "misspelled_person_name",
        "Tell me about Hannes Leitgib.",  # typo for "Hannes Leitgeb"
        set(),  # exact search_people misses the typo → fuzzy fallback / fuzzy_search resolves it
        ["leitgeb"],  # the CORRECTED name must surface — verifies typo tolerance end-to-end
    ),
]


def run_case(engine: ChatEngine, label: str, query: str, expected_tools: set, must_contain: list):
    calls: list[tuple[str, dict]] = []

    def cb(tool_name, args):
        calls.append((tool_name, dict(args) if args else {}))

    t0 = time.time()
    error = None
    response = ""
    try:
        response = engine.generate_response(
            query,
            use_mcp_tools=True,
            model_name=DEFAULT_GEMINI_MODEL,
            chat_history=None,
            status_callback=cb,
        )
    except Exception as e:
        error = repr(e)
    elapsed = time.time() - t0

    tools_fired = {c[0] for c in calls}
    missing_expected = expected_tools - tools_fired
    any_tool_fired = bool(tools_fired)
    content_ok = all(s in response.lower() for s in must_contain) if response else False
    # The engine swallows exceptions and returns "Error: ..." strings — treat those as failures.
    response_is_error = response.lstrip().startswith("Error:")

    # PASS criteria:
    # - no exception, no "Error:" response
    # - if expected_tools non-empty: all expected tools fired
    # - if expected_tools empty: at least one tool fired (we always want tool use here)
    # - any required substrings appear in response
    if error:
        verdict = "ERROR"
    elif response_is_error:
        verdict = "FAIL_RESPONSE_ERROR"
    elif expected_tools and missing_expected:
        verdict = "FAIL_TOOLS"
    elif not expected_tools and not any_tool_fired:
        verdict = "FAIL_NO_TOOLS"
    elif must_contain and not content_ok:
        verdict = "FAIL_CONTENT"
    else:
        verdict = "PASS"

    return {
        "label": label,
        "query": query,
        "verdict": verdict,
        "tools_fired": calls,
        "missing_expected": sorted(missing_expected),
        "elapsed_s": round(elapsed, 2),
        "error": error,
        "response_preview": (response or "")[:240].replace("\n", " "),
    }


def main():
    print(f"Initializing ChatEngine (provider=gemini, model={DEFAULT_GEMINI_MODEL})...")
    engine = ChatEngine(use_mcp=True, provider="gemini")
    print(f"Running {len(CASES)} stress cases.\n")

    results = []
    for label, query, expected_tools, must_contain in CASES:
        print(f"--- {label} ---")
        print(f"Q: {query}")
        r = run_case(engine, label, query, expected_tools, must_contain)
        results.append(r)
        print(f"  verdict       : {r['verdict']}  ({r['elapsed_s']}s)")
        if r["tools_fired"]:
            for tn, args in r["tools_fired"]:
                # Show just key arg fields to keep output short
                key_args = {k: (str(v)[:60] + "…") if isinstance(v, str) and len(str(v)) > 60 else v
                            for k, v in args.items()}
                print(f"    tool        : {tn}({key_args})")
        else:
            print("    tool        : (none)")
        if r["missing_expected"]:
            print(f"    missing     : {r['missing_expected']}")
        if r["error"]:
            print(f"    error       : {r['error']}")
        print(f"    response    : {r['response_preview']}")
        print()
        time.sleep(1.0)  # polite pacing — avoid bursts

    # Summary
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    total = len(results)
    passed = counts.get("PASS", 0)

    print("=" * 70)
    print(f"SUMMARY  ({passed}/{total} passed)")
    for verdict, n in sorted(counts.items()):
        print(f"  {verdict:15s} {n}")
    print()
    avg_latency = sum(r["elapsed_s"] for r in results) / total
    print(f"Average latency: {avg_latency:.2f}s")
    print()
    print("Failures:")
    failures = [r for r in results if r["verdict"] != "PASS"]
    if not failures:
        print("  (none)")
    for r in failures:
        print(f"  - {r['label']}: {r['verdict']}  | tools={[t[0] for t in r['tools_fired']]}  | missing={r['missing_expected']}")
        if r["error"]:
            print(f"    error: {r['error']}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
