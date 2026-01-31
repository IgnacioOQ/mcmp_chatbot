from typing import List, Dict, Any
from src.mcp.tools import search_people, search_research, get_events
import json

class MCPServer:
    """
    In-process MCP Server interface.
    Exposes MCMP data tools to the RAG functionality.
    """
    
    def __init__(self):
        self.tools = {
            "search_people": search_people,
            "search_research": search_research,
            "get_events": get_events
        }
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Returns the tool definitions in OpenAI/MCP-compatible format.
        """
        return [
            {
                "name": "search_people",
                "description": "Search for people, faculty, and researchers at the MCMP. Use this to find contact info, roles, or research interests of specific individuals.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Name or keyword to search for (e.g., 'Julian Nida-Rumelin', 'Logic')."
                        },
                        "role_filter": {
                            "type": "string",
                            "description": "Optional filter for role (e.g., 'Chair', 'Postdoc', 'Fellow')."
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_research",
                "description": "Explore research topics, areas, and projects at the MCMP.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Research topic to filter by (e.g., 'Philosophy of Physics', 'Decision Theory')."
                        }
                    }
                }
            },
            {
                "name": "get_events",
                "description": "Get a list of upcoming or past events, talks, and workshops. Can filter by specific date ranges.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "date_range": {
                            "type": "string",
                            "enum": ["upcoming", "today", "this_week"],
                            "description": "Preset relative time range. Default is 'upcoming'. Ignored if specific dates are provided."
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date for filtering events (format: YYYY-MM-DD). Useful for queries like 'events after Oct 5th' or 'events in December'."
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date for filtering events (format: YYYY-MM-DD). Use with start_date for specific ranges."
                        },
                        "type_filter": {
                            "type": "string",
                            "description": "Filter by event type (e.g., 'Talk', 'Workshop')."
                        }
                    }
                }
            }
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Executes a tool by name with provided arguments.
        """
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")
            
        tool_func = self.tools[name]
        try:
            return tool_func(**arguments)
        except Exception as e:
            return {"error": str(e)}
