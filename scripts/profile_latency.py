"""
MCMP Chatbot — End-to-End Latency Profiler
==========================================
Measures wall-clock time for each stage of the pipeline:
  1. Engine initialisation (startup cost)
  2. Personality load (per-call cost)
  3. MCP tool execution (JSON search speed)
  4. Gemini client creation (per-call overhead)
  5. Full generate_response() round-trip (cold + warm)

Run with:
    python scripts/profile_latency.py [--query "your query here"]

Results are printed as a formatted table and written to scripts/latency_report.json.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

# ── ensure project root is on the path ──────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── colour helpers (no external deps) ───────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def colour(ms: float, warn=500, bad=1500) -> str:
    if ms < warn:
        return f"{GREEN}{ms:7.1f} ms{RESET}"
    if ms < bad:
        return f"{YELLOW}{ms:7.1f} ms{RESET}"
    return f"{RED}{ms:7.1f} ms{RESET}"

def banner(title: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")

def timer(label: str, fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"  {'·'} {label:<42} {colour(elapsed_ms)}")
    return result, elapsed_ms


# ── individual stage benchmarks ─────────────────────────────────────────────

def bench_engine_init():
    banner("Stage 1 · Engine Initialisation")
    from src.core.engine import ChatEngine

    _, ms_mcp_on = timer(
        "ChatEngine(use_mcp=True)",
        ChatEngine, use_mcp=True, provider="gemini"
    )
    _, ms_mcp_off = timer(
        "ChatEngine(use_mcp=False)",
        ChatEngine, use_mcp=False, provider="gemini"
    )
    print(f"    MCP overhead on init: {ms_mcp_on - ms_mcp_off:.1f} ms")
    return {"engine_init_mcp_on_ms": ms_mcp_on, "engine_init_mcp_off_ms": ms_mcp_off}


def bench_personality():
    banner("Stage 2 · Personality Load (per-call cost)")
    from src.core.personality import load_personality

    _, ms1 = timer("load_personality() — cold", load_personality)
    _, ms2 = timer("load_personality() — warm (repeat)", load_personality)
    _, ms3 = timer("load_personality() — warm (repeat)", load_personality)
    return {
        "personality_cold_ms": ms1,
        "personality_warm_ms": (ms2 + ms3) / 2,
    }


def bench_mcp_tools():
    banner("Stage 3 · MCP Tool Execution (local JSON search)")
    from src.mcp.tools import search_people, search_research, get_events, search_graph

    results = {}

    _, ms = timer("search_people('Leitgeb')", search_people, "Leitgeb")
    results["search_people_ms"] = ms

    _, ms = timer("search_people('Ignacio')", search_people, "Ignacio")
    results["search_people_partial_ms"] = ms

    _, ms = timer("search_research('Logic')", search_research, "Logic")
    results["search_research_ms"] = ms

    _, ms = timer("get_events(date_range='upcoming')", get_events, date_range="upcoming")
    results["get_events_upcoming_ms"] = ms

    _, ms = timer("get_events(start_date='2026-03-01', end_date='2026-06-01')",
                  get_events, start_date="2026-03-01", end_date="2026-06-01")
    results["get_events_date_range_ms"] = ms

    _, ms = timer("search_graph('Leitgeb')", search_graph, "Leitgeb")
    results["search_graph_ms"] = ms

    return results


def bench_gemini_client():
    banner("Stage 4 · Gemini Client + Chat Creation (per-call overhead)")
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("  ⚠  GEMINI_API_KEY not found — skipping this stage.")
        return {}

    results = {}

    def _import_and_create_client():
        from google import genai
        return genai.Client(api_key=api_key)

    client, ms = timer("import google.genai + Client()", _import_and_create_client)
    results["gemini_import_and_client_ms"] = ms

    from google import genai
    from google.genai import types

    def _create_chat():
        return client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction="You are a helpful assistant.",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False, maximum_remote_calls=3
                )
            )
        )

    _, ms1 = timer("client.chats.create() — first", _create_chat)
    _, ms2 = timer("client.chats.create() — second", _create_chat)
    results["gemini_chat_create_cold_ms"] = ms1
    results["gemini_chat_create_warm_ms"] = ms2

    return results


def bench_full_pipeline(query: str, runs: int = 2):
    banner(f"Stage 5 · Full generate_response() — {runs} runs")
    from src.core.engine import ChatEngine

    print(f"  Query: \"{query}\"")

    # Pre-create engine so we measure per-call not init
    engine = ChatEngine(use_mcp=True, provider="gemini")
    print()

    results = {}
    times = []
    for i in range(runs):
        label = "cold start" if i == 0 else f"run {i+1}"
        _, ms = timer(f"generate_response() [{label}]", engine.generate_response,
                      query, use_mcp_tools=True)
        times.append(ms)

    results["full_pipeline_runs_ms"] = times
    results["full_pipeline_avg_ms"] = sum(times) / len(times)
    results["full_pipeline_min_ms"] = min(times)
    return results


# ── summary table ────────────────────────────────────────────────────────────

def print_summary(all_results: dict):
    banner("Summary — Bottleneck Report")

    # Flatten notable metrics with human labels
    entries = [
        ("Engine init (MCP on)",         all_results.get("engine_init_mcp_on_ms")),
        ("Engine init (MCP off)",         all_results.get("engine_init_mcp_off_ms")),
        ("Personality load — cold",       all_results.get("personality_cold_ms")),
        ("Personality load — warm",       all_results.get("personality_warm_ms")),
        ("search_people()",               all_results.get("search_people_ms")),
        ("search_research()",             all_results.get("search_research_ms")),
        ("get_events() upcoming",         all_results.get("get_events_upcoming_ms")),
        ("get_events() date range",       all_results.get("get_events_date_range_ms")),
        ("search_graph()",                all_results.get("search_graph_ms")),
        ("Gemini import+client create",   all_results.get("gemini_import_and_client_ms")),
        ("Gemini chat.create() cold",     all_results.get("gemini_chat_create_cold_ms")),
        ("Gemini chat.create() warm",     all_results.get("gemini_chat_create_warm_ms")),
        ("Full pipeline — best run",      all_results.get("full_pipeline_min_ms")),
        ("Full pipeline — average",       all_results.get("full_pipeline_avg_ms")),
    ]

    print(f"\n  {'Metric':<44} {'Time':>10}")
    print(f"  {'─'*44} {'─'*10}")
    for label, val in entries:
        if val is not None:
            print(f"  {label:<44} {colour(val)}")
        else:
            print(f"  {label:<44}     N/A")

    # Highlight top bottlenecks
    measurable = [(l, v) for l, v in entries if v is not None]
    if measurable:
        top = sorted(measurable, key=lambda x: x[1], reverse=True)[:3]
        print(f"\n{BOLD}  Top bottlenecks:{RESET}")
        for rank, (label, val) in enumerate(top, 1):
            print(f"    {rank}. {label}: {val:.0f} ms")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Profile MCMP Chatbot latency.")
    parser.add_argument("--query", default="What is the next upcoming talk?",
                        help="Query to use for the full pipeline benchmark.")
    parser.add_argument("--runs", type=int, default=2,
                        help="Number of full-pipeline runs (default: 2).")
    parser.add_argument("--skip-full", action="store_true",
                        help="Skip the full generate_response() benchmark (saves API calls).")
    args = parser.parse_args()

    print(f"\n{BOLD}MCMP Chatbot — Latency Profiler{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Query    : {args.query}")

    all_results = {"timestamp": datetime.now().isoformat(), "query": args.query}

    try:
        all_results.update(bench_engine_init())
    except Exception as e:
        print(f"  ERROR in engine init bench: {e}")

    try:
        all_results.update(bench_personality())
    except Exception as e:
        print(f"  ERROR in personality bench: {e}")

    try:
        all_results.update(bench_mcp_tools())
    except Exception as e:
        print(f"  ERROR in MCP tools bench: {e}")

    try:
        all_results.update(bench_gemini_client())
    except Exception as e:
        print(f"  ERROR in Gemini client bench: {e}")

    if not args.skip_full:
        try:
            all_results.update(bench_full_pipeline(args.query, runs=args.runs))
        except Exception as e:
            print(f"  ERROR in full pipeline bench: {e}")

    print_summary(all_results)

    # Write JSON report
    report_path = os.path.join(ROOT, "scripts", "latency_report.json")
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Report saved → {report_path}\n")


if __name__ == "__main__":
    main()
