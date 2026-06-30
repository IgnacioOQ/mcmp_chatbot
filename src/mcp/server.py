from typing import List, Dict, Any, Tuple
from src.mcp.tools import search_people, search_research, get_events, search_graph, grep_data, fuzzy_search, ask_clarification, search_academic_offerings
from src.utils.logger import log_latency
import json

class MCPServer:
    """
    In-process MCP Server interface.
    Exposes MCMP data tools to the chat engine.
    """
    
    def __init__(self):
        self.tools = {
            "ask_clarification": ask_clarification,
            "search_people": search_people,
            "search_research": search_research,
            "get_events": get_events,
            "search_graph": search_graph,
            "grep_data": grep_data,
            "fuzzy_search": fuzzy_search,
            "search_academic_offerings": search_academic_offerings,
        }
        # Per-request dedupe cache: (tool_name, frozen_args) -> result.
        # The engine clears this at the start of each generate_response call
        # so the cache lives only for the duration of one user query.
        self._call_cache: Dict[Tuple[str, Any], Any] = {}

    def reset_call_cache(self) -> None:
        """Clear the per-request tool-result cache. Call before each user query."""
        self._call_cache.clear()

    @staticmethod
    def _freeze_args(args: Dict[str, Any]) -> Tuple:
        """Make tool arguments hashable for cache keying. Lists/dicts → tuples."""
        def _f(v):
            if isinstance(v, dict):
                return tuple(sorted((k, _f(x)) for k, x in v.items()))
            if isinstance(v, list):
                return tuple(_f(x) for x in v)
            return v
        return tuple(sorted((k, _f(v)) for k, v in (args or {}).items()))
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Returns the tool definitions in OpenAI/MCP-compatible format.
        """
        return [
            {
                "name": "ask_clarification",
                "description": (
                    "Ask the user a clarification question BEFORE searching any database. "
                    "Use this when: (1) a query is ambiguous (e.g. a name matches multiple people), "
                    "(2) the user's intent is unclear and wrong tool selection would waste a turn, "
                    "or (3) the request could be interpreted in fundamentally different ways. "
                    "Do NOT use this for straightforward lookups — only when genuine ambiguity exists. "
                    "Do NOT use this for read-only or simple factual questions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": (
                                "A clear, concise disambiguation question for the user. "
                                "Explain what additional context you need and why. "
                                "Example: 'I found two people with the name Landes — "
                                "Jürgen Landes (philosopher) and another. Which do you mean?'"
                            )
                        }
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "search_people",
                "description": (
                    "Search for MCMP researchers, faculty, staff, and doctoral fellows by name or research keyword. "
                    "Use for any question about a specific person — their role, email, office, publications, or research. "
                    "ALWAYS call this when the user mentions a person's name, even if partial (first name, last name, or with a title like Dr./Prof.). "
                    "Also use to find people working on a specific topic (e.g. 'who works on Bayesianism?'). "
                    "IMPORTANT: extract only the name or keyword from the user's message — do NOT pass the full user sentence as the query."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The person's name or a research keyword — extracted from the user's message. "
                                "If the user says 'tell me about a researcher named Landes', pass 'Landes'. "
                                "If they say 'who works on probability', pass 'probability'. "
                                "Examples: 'Landes', 'Christian List', 'Hannes Leitgeb', 'logic', 'decision theory'."
                            )
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_research",
                "description": (
                    "Explore MCMP research areas, topics, and projects. "
                    "Use when the user asks about a field of research rather than a specific person — "
                    "e.g. 'What does the MCMP work on?', 'Tell me about the Philosophy of Science group', 'What subtopics exist under Logic?'. "
                    "Covers Logic & Philosophy of Language, Philosophy of Science, Decision Theory, Mathematical Philosophy, and their subtopics."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": (
                                "Research area or keyword to filter by. Leave empty to list all areas. "
                                "Examples: 'Logic', 'Bayesianism', 'Philosophy of Physics', 'Decision Theory'."
                            )
                        }
                    }
                }
            },
            {
                "name": "search_graph",
                "description": (
                    "Search the MCMP institutional graph for organizational relationships. "
                    "Use to answer: who leads a chair, who supervises whom, which chair a person belongs to, "
                    "or who is affiliated with an organizational unit. "
                    "Best used AFTER search_people when you need organizational context beyond biographical info."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Name of the person or organizational unit. "
                                "Examples: 'Hannes Leitgeb', 'Chair of Logic and Philosophy of Language', 'MCMP'."
                            )
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_events",
                "description": (
                    "Get upcoming events, talks, workshops, and reading groups at the MCMP. "
                    "Returns detailed info: title, speaker, date, location, abstract. "
                    "Use for any question about schedule, upcoming talks, or events involving a specific person or topic."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date_range": {
                            "type": "string",
                            "enum": ["upcoming", "today", "this_week"],
                            "description": "Preset time range. Default is 'upcoming'. Ignored if start_date/end_date are provided."
                        },
                        "query": {
                            "type": "string",
                            "description": (
                                "Keyword to search in event title, speaker name, or abstract. "
                                "Extract just the name or topic — not the full user sentence. "
                                "Examples: 'quantum mechanics', 'Landes', 'decision theory'."
                            )
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format. Use for 'events after March 10th' or 'events in April'."
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format. Use with start_date for a specific range."
                        },
                        "type_filter": {
                            "type": "string",
                            "description": "Filter by event type. Examples: 'Talk', 'Workshop', 'Reading Group'."
                        }
                    }
                }
            },
            {
                "name": "search_academic_offerings",
                "description": (
                    "Search academic program information at the MCMP: degree programs, application requirements, "
                    "deadlines, coordinators, required documents, and learning materials. "
                    "Use for any question about the Master in Logic and Philosophy of Science, "
                    "the Bachelor in Philosophy, PhD application pathways, or study resources. "
                    "Examples: 'How do I apply for the Master program?', 'What are the PhD application contacts?', "
                    "'What is the application deadline?', 'What documents are needed to apply?'"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Keyword or phrase to search across program descriptions and metadata. "
                                "Examples: 'application deadline', 'ECTS', 'required documents', 'logic', 'PhD'."
                            )
                        },
                        "offering_type": {
                            "type": "string",
                            "enum": ["master", "bachelor", "phd", "learning_materials"],
                            "description": "Optional filter by program type."
                        }
                    }
                }
            },
            {
                "name": "grep_data",
                "description": (
                    "Flexible grep-style search across MCMP databases. "
                    "Scans the full text of records (bios, abstracts, publications, metadata) "
                    "and returns snippets showing exactly where the pattern occurs. "
                    "Use this when the other tools are too narrow — e.g. to find anyone who "
                    "mentions a specific institution, grant, journal name, or exact phrase. "
                    "Prefer plain substring (use_regex=false) unless you specifically need "
                    "a regex pattern. Narrow the search with 'database' to avoid noise."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": (
                                "The keyword or regex pattern to search for. "
                                "Examples: 'Bayesianism', 'DFG', 'quantum gravity', r'\\bLogic\\b'."
                            )
                        },
                        "database": {
                            "type": "string",
                            "enum": ["all", "people", "research", "events", "academic_offerings"],
                            "description": "Which database to search. Default is 'all'."
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional list of field name substrings to restrict search. "
                                "E.g. ['description', 'selected_publications'] to skip metadata fields."
                            )
                        },
                        "use_regex": {
                            "type": "boolean",
                            "description": "If true, treat pattern as a Python regex (case-insensitive). Default false."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of snippets to return. Default 10."
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "fuzzy_search",
                "description": (
                    "Typo-tolerant (approximate) NAME search across MCMP databases using edit-distance matching. "
                    "Returns the closest-matching names ranked by a similarity score, even when the spelling is wrong. "
                    "Use this as a FALLBACK when an exact tool (search_people, get_events, search_research) returns "
                    "nothing and the query is a name that might be misspelled — e.g. 'Tom Sternkenberg' surfaces "
                    "'Tom F. Sterkenburg'. Take the returned `name` and re-query the precise tool for full details. "
                    "Do NOT use this as a first resort, and NOT for topic/free-text search (use search_people or grep_data for those)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "The possibly-misspelled name to match. Extract just the name, not the full sentence. "
                                "Examples: 'Sternkenberg', 'Leitgib', 'Nida Rumelin'."
                            )
                        },
                        "database": {
                            "type": "string",
                            "enum": ["people", "events", "research", "all"],
                            "description": (
                                "Which database of names to match against. 'people' (default) for person names, "
                                "'events' for speaker names / talk titles, 'research' for area names, or 'all'."
                            )
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of ranked matches to return. Default 5."
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum similarity 0-1 to include. Default 0.6; lower (~0.45) for very garbled input."
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any],
                  status_callback=None) -> Any:
        """
        Executes a tool by name with provided arguments.
        status_callback: optional callable(tool_name, arguments) fired before execution.
        """
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")

        if status_callback:
            try:
                status_callback(name, arguments)
            except Exception:
                pass  # Never let UI code break tool execution

        # Per-request dedupe: identical (name, args) within a single user query
        # returns the cached result instead of re-invoking the tool. Some
        # frontier models speculatively repeat tool calls, which doubles
        # latency for no benefit.
        cache_key = (name, self._freeze_args(arguments))
        if cache_key in self._call_cache:
            return self._call_cache[cache_key]

        tool_func = self.tools[name]
        try:
            with log_latency(f"tool:{name}"):
                result = tool_func(**arguments)
            self._call_cache[cache_key] = result
            return result
        except Exception as e:
            return {"error": str(e)}

    def get_instrumented_tools(self, status_callback) -> list:
        """
        Returns wrapped versions of the tool functions that fire status_callback
        before executing. Used by the Gemini automatic_function_calling path,
        where the SDK calls the raw Python functions directly.
        """
        import functools
        instrumented = []
        for name, fn in self.tools.items():
            @functools.wraps(fn)
            def _wrapper(*args, _name=name, _fn=fn, **kwargs):
                try:
                    status_callback(_name, kwargs)
                except Exception:
                    pass
                # Per-request dedupe — see call_tool() for rationale.
                cache_key = (_name, self._freeze_args(kwargs))
                if cache_key in self._call_cache:
                    return self._call_cache[cache_key]
                result = _fn(*args, **kwargs)
                self._call_cache[cache_key] = result
                return result
            instrumented.append(_wrapper)
        return instrumented
