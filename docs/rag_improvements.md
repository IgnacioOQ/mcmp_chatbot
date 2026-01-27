# RAG Performance Improvements for MCMP Chatbot

Two simple, cost-effective strategies to improve your RAG chatbot's performance.

---

## Strategy 1: Chain-of-Thought / Multi-Step Retrieval

The core idea: instead of doing a single retrieval pass, make the LLM "think" about what information it needs and explore the database iteratively.

### Option A: Query Decomposition (Cheapest)

Before retrieval, ask the LLM to break down the user's question into sub-queries.

```python
# src/core/engine.py - Add this function

def decompose_query(user_question: str, llm_client) -> list[str]:
    """
    Decompose a complex question into simpler sub-queries.
    This helps retrieve more relevant chunks from the vector store.
    
    Args:
        user_question: The original user question
        llm_client: Your Gemini/OpenAI client
    
    Returns:
        List of sub-queries to search for
    """
    # This prompt is cheap - uses minimal tokens
    decomposition_prompt = f"""Given this question about MCMP (Munich Center for Mathematical Philosophy):
"{user_question}"

Break it into 1-3 simple search queries that would help find relevant information.
Return ONLY the queries, one per line, no numbering or bullets.
If the question is already simple, just return it as-is."""
    
    response = llm_client.generate_content(decomposition_prompt)
    
    # Parse the response into individual queries
    queries = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
    
    # Always include the original query too
    if user_question not in queries:
        queries.insert(0, user_question)
    
    return queries[:4]  # Cap at 4 queries to control costs


def retrieve_with_decomposition(user_question: str, vector_store, llm_client, top_k: int = 3) -> list[dict]:
    """
    Retrieve relevant chunks using query decomposition.
    
    Args:
        user_question: Original user question
        vector_store: ChromaDB vector store instance
        llm_client: LLM client for decomposition
        top_k: Number of results per query
    
    Returns:
        Deduplicated list of relevant chunks
    """
    # Step 1: Decompose the query
    queries = decompose_query(user_question, llm_client)
    
    # Step 2: Retrieve for each sub-query
    all_chunks = []
    seen_ids = set()
    
    for query in queries:
        results = vector_store.query(query_texts=[query], n_results=top_k)
        
        # Deduplicate by document ID
        for i, doc_id in enumerate(results['ids'][0]):
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_chunks.append({
                    'id': doc_id,
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'source_query': query  # Track which query found this
                })
    
    return all_chunks
```

### Option B: Self-Ask Pattern (Slightly More Expensive)

The LLM generates follow-up questions and answers them iteratively.

```python
# src/core/engine.py - Add this function

def self_ask_retrieval(user_question: str, vector_store, llm_client, max_steps: int = 2) -> str:
    """
    Implement Self-Ask pattern: the LLM asks itself follow-up questions
    and retrieves information to answer them.
    
    This is more thorough but uses more API calls.
    
    Args:
        user_question: Original user question
        vector_store: ChromaDB instance
        llm_client: LLM client
        max_steps: Maximum follow-up iterations (keep low for cost control)
    
    Returns:
        Final answer string
    """
    # Collect all retrieved context across steps
    accumulated_context = []
    
    # Initial retrieval
    initial_results = vector_store.query(query_texts=[user_question], n_results=5)
    accumulated_context.extend(initial_results['documents'][0])
    
    # Iterative self-asking
    current_question = user_question
    
    for step in range(max_steps):
        # Ask the LLM if it needs more information
        check_prompt = f"""Based on this question: "{current_question}"

And this context I've found:
{chr(10).join(accumulated_context[-5:])}

Do you need to search for additional information to answer fully?
If YES, respond with: SEARCH: [your search query]
If NO, respond with: READY

Be concise."""
        
        check_response = llm_client.generate_content(check_prompt)
        response_text = check_response.text.strip()
        
        if response_text.startswith("SEARCH:"):
            # Extract the follow-up query and retrieve more context
            follow_up_query = response_text.replace("SEARCH:", "").strip()
            follow_up_results = vector_store.query(
                query_texts=[follow_up_query], 
                n_results=3
            )
            
            # Add new context (deduplicated)
            for doc in follow_up_results['documents'][0]:
                if doc not in accumulated_context:
                    accumulated_context.append(doc)
        else:
            # LLM says it's ready
            break
    
    # Generate final answer with all accumulated context
    final_prompt = f"""Answer this question about MCMP (Munich Center for Mathematical Philosophy):
"{user_question}"

Use ONLY this information:
{chr(10).join(accumulated_context)}

If the information doesn't contain the answer, say so clearly."""
    
    final_response = llm_client.generate_content(final_prompt)
    return final_response.text
```

### Option C: Step-Back Prompting (Best Quality/Cost Ratio)

Ask for a more abstract version of the question first, retrieve for both.

```python
# src/core/engine.py - Add this function

def step_back_retrieval(user_question: str, vector_store, llm_client, top_k: int = 3) -> list[dict]:
    """
    Step-Back Prompting: generate a more general/abstract version of the question
    and retrieve for both the original and the abstracted version.
    
    This often catches context that keyword-based retrieval misses.
    
    Args:
        user_question: Original specific question
        vector_store: ChromaDB instance
        llm_client: LLM client
        top_k: Results per query
    
    Returns:
        Combined context from both queries
    """
    # Generate a step-back (more abstract) question
    step_back_prompt = f"""Given this specific question about MCMP:
"{user_question}"

What is a more general question that would help provide context for answering this?
For example:
- "When is Dr. Smith's next talk?" → "What talks are scheduled at MCMP?"
- "Does the reading group meet this Thursday?" → "What reading groups exist at MCMP?"

Respond with ONLY the general question, nothing else."""
    
    response = llm_client.generate_content(step_back_prompt)
    abstract_question = response.text.strip()
    
    # Retrieve for both questions
    all_chunks = []
    seen_texts = set()
    
    for query in [user_question, abstract_question]:
        results = vector_store.query(query_texts=[query], n_results=top_k)
        
        for i, doc in enumerate(results['documents'][0]):
            # Simple deduplication by text content
            doc_hash = hash(doc[:100])  # Hash first 100 chars
            if doc_hash not in seen_texts:
                seen_texts.add(doc_hash)
                all_chunks.append({
                    'text': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'query_type': 'original' if query == user_question else 'step_back'
                })
    
    return all_chunks
```

---

## Strategy 2: MCP-Based Data Enhancement

The idea: create an MCP server that exposes your MCMP data as structured tools, letting the LLM query it more intelligently.

### Why MCP for RAG?

Instead of dumping text chunks to the LLM, MCP lets you expose **semantic operations**:
- `get_upcoming_events(days=7)` - Returns structured event data
- `find_person(name)` - Returns structured person info
- `search_by_topic(topic)` - Semantic search with filtering

This is more informative because the LLM can **chain tool calls** and get **structured responses**.

### Simple MCP Server for MCMP Data

```python
# mcp_server/mcmp_server.py
"""
MCP Server that exposes MCMP data as structured tools.
This gives the LLM better ways to explore and query the data.

Run with: python -m mcp_server.mcmp_server
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize the MCP server
server = Server("mcmp-data-server")

# Path to your scraped data (adjust as needed)
DATA_DIR = Path(__file__).parent.parent / "data"


def load_events() -> list[dict]:
    """Load events from JSON files in the data directory."""
    events = []
    events_file = DATA_DIR / "events.json"
    if events_file.exists():
        with open(events_file, 'r') as f:
            events = json.load(f)
    return events


def load_people() -> list[dict]:
    """Load people data from JSON files."""
    people = []
    people_file = DATA_DIR / "people.json"
    if people_file.exists():
        with open(people_file, 'r') as f:
            people = json.load(f)
    return people


def load_reading_groups() -> list[dict]:
    """Load reading group data."""
    groups = []
    groups_file = DATA_DIR / "reading_groups.json"
    if groups_file.exists():
        with open(groups_file, 'r') as f:
            groups = json.load(f)
    return groups


# Define the tools the LLM can use
@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    List all available tools for querying MCMP data.
    These provide structured access to the scraped data.
    """
    return [
        Tool(
            name="get_upcoming_events",
            description="Get upcoming events at MCMP. Returns talks, seminars, and other events within the specified number of days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 14)",
                        "default": 14
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type: 'talk', 'seminar', 'reading_group', 'workshop', or 'all'",
                        "default": "all"
                    }
                }
            }
        ),
        Tool(
            name="find_person",
            description="Find information about a person at MCMP by name. Returns their role, research interests, contact info, and upcoming activities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name or partial name of the person to find"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="search_by_topic",
            description="Search MCMP activities by research topic or keyword. Returns relevant events, people, and reading groups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Research topic or keyword to search for (e.g., 'epistemology', 'logic', 'philosophy of science')"
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="get_reading_groups",
            description="Get information about MCMP reading groups, including their topics, meeting times, and current readings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Only return currently active reading groups",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="get_event_details",
            description="Get detailed information about a specific event by its title or ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_title": {
                        "type": "string",
                        "description": "Title or partial title of the event"
                    }
                },
                "required": ["event_title"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Handle tool calls from the LLM.
    Each tool returns structured, informative data.
    """
    
    if name == "get_upcoming_events":
        days = arguments.get("days", 14)
        event_type = arguments.get("event_type", "all")
        
        events = load_events()
        today = datetime.now()
        cutoff = today + timedelta(days=days)
        
        # Filter events by date and type
        upcoming = []
        for event in events:
            try:
                event_date = datetime.fromisoformat(event.get('date', ''))
                if today <= event_date <= cutoff:
                    if event_type == "all" or event.get('type', '').lower() == event_type.lower():
                        upcoming.append(event)
            except (ValueError, TypeError):
                continue
        
        # Sort by date
        upcoming.sort(key=lambda x: x.get('date', ''))
        
        if not upcoming:
            return [TextContent(
                type="text",
                text=f"No events found in the next {days} days."
            )]
        
        # Format response
        result = f"## Upcoming MCMP Events (next {days} days)\n\n"
        for event in upcoming[:10]:  # Limit to 10
            result += f"### {event.get('title', 'Untitled')}\n"
            result += f"- **Date**: {event.get('date', 'TBA')}\n"
            result += f"- **Time**: {event.get('time', 'TBA')}\n"
            result += f"- **Speaker**: {event.get('speaker', 'TBA')}\n"
            result += f"- **Location**: {event.get('location', 'TBA')}\n"
            if event.get('abstract'):
                result += f"- **Abstract**: {event.get('abstract', '')[:200]}...\n"
            result += "\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "find_person":
        search_name = arguments.get("name", "").lower()
        people = load_people()
        
        # Fuzzy match on name
        matches = []
        for person in people:
            full_name = person.get('name', '').lower()
            if search_name in full_name or any(
                part in full_name for part in search_name.split()
            ):
                matches.append(person)
        
        if not matches:
            return [TextContent(
                type="text",
                text=f"No person found matching '{arguments.get('name')}'."
            )]
        
        # Format response
        result = ""
        for person in matches[:3]:  # Limit to 3 matches
            result += f"## {person.get('name', 'Unknown')}\n"
            result += f"- **Role**: {person.get('role', 'Not specified')}\n"
            result += f"- **Email**: {person.get('email', 'Not available')}\n"
            if person.get('research_interests'):
                result += f"- **Research Interests**: {', '.join(person.get('research_interests', []))}\n"
            if person.get('bio'):
                result += f"- **Bio**: {person.get('bio', '')[:300]}...\n"
            result += "\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "search_by_topic":
        topic = arguments.get("topic", "").lower()
        
        results = {"events": [], "people": [], "reading_groups": []}
        
        # Search events
        events = load_events()
        for event in events:
            searchable = f"{event.get('title', '')} {event.get('abstract', '')} {event.get('speaker', '')}".lower()
            if topic in searchable:
                results["events"].append(event)
        
        # Search people
        people = load_people()
        for person in people:
            searchable = f"{person.get('name', '')} {person.get('bio', '')} {' '.join(person.get('research_interests', []))}".lower()
            if topic in searchable:
                results["people"].append(person)
        
        # Search reading groups
        groups = load_reading_groups()
        for group in groups:
            searchable = f"{group.get('name', '')} {group.get('topic', '')} {group.get('description', '')}".lower()
            if topic in searchable:
                results["reading_groups"].append(group)
        
        # Format response
        output = f"## Search Results for '{topic}'\n\n"
        
        if results["events"]:
            output += f"### Related Events ({len(results['events'])} found)\n"
            for event in results["events"][:5]:
                output += f"- **{event.get('title', 'Untitled')}** ({event.get('date', 'TBA')})\n"
            output += "\n"
        
        if results["people"]:
            output += f"### Related People ({len(results['people'])} found)\n"
            for person in results["people"][:5]:
                output += f"- **{person.get('name', 'Unknown')}** - {person.get('role', '')}\n"
            output += "\n"
        
        if results["reading_groups"]:
            output += f"### Related Reading Groups ({len(results['reading_groups'])} found)\n"
            for group in results["reading_groups"][:3]:
                output += f"- **{group.get('name', 'Unknown')}**: {group.get('topic', '')}\n"
            output += "\n"
        
        if not any(results.values()):
            output = f"No results found for topic '{topic}'."
        
        return [TextContent(type="text", text=output)]
    
    elif name == "get_reading_groups":
        active_only = arguments.get("active_only", True)
        groups = load_reading_groups()
        
        if active_only:
            groups = [g for g in groups if g.get('active', True)]
        
        if not groups:
            return [TextContent(type="text", text="No reading groups found.")]
        
        result = "## MCMP Reading Groups\n\n"
        for group in groups:
            result += f"### {group.get('name', 'Unnamed Group')}\n"
            result += f"- **Topic**: {group.get('topic', 'Not specified')}\n"
            result += f"- **Meeting Time**: {group.get('meeting_time', 'TBA')}\n"
            result += f"- **Organizer**: {group.get('organizer', 'TBA')}\n"
            if group.get('current_reading'):
                result += f"- **Current Reading**: {group.get('current_reading')}\n"
            result += "\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "get_event_details":
        search_title = arguments.get("event_title", "").lower()
        events = load_events()
        
        # Find matching event
        for event in events:
            if search_title in event.get('title', '').lower():
                result = f"## {event.get('title', 'Untitled')}\n\n"
                result += f"- **Date**: {event.get('date', 'TBA')}\n"
                result += f"- **Time**: {event.get('time', 'TBA')}\n"
                result += f"- **Location**: {event.get('location', 'TBA')}\n"
                result += f"- **Speaker**: {event.get('speaker', 'TBA')}\n"
                result += f"- **Type**: {event.get('type', 'Event')}\n"
                if event.get('abstract'):
                    result += f"\n### Abstract\n{event.get('abstract')}\n"
                if event.get('bio'):
                    result += f"\n### Speaker Bio\n{event.get('bio')}\n"
                
                return [TextContent(type="text", text=result)]
        
        return [TextContent(
            type="text",
            text=f"No event found matching '{arguments.get('event_title')}'."
        )]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcmp-data-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### MCP Server Configuration

Add this to your project root as `mcp_config.json`:

```json
{
  "mcpServers": {
    "mcmp-data": {
      "command": "python",
      "args": ["-m", "mcp_server.mcmp_server"],
      "cwd": "/path/to/mcmp_chatbot"
    }
  }
}
```

### Integrating MCP with Your Existing Chatbot

```python
# src/core/mcp_integration.py
"""
Integration layer to use MCP tools from your existing chatbot.
This wraps the MCP server calls in a way that works with your engine.py
"""

import subprocess
import json
from typing import Optional


class MCMPToolRunner:
    """
    Runs MCP tools and returns structured results.
    This is a simplified approach that doesn't require full MCP client setup.
    """
    
    def __init__(self, data_dir: str):
        """
        Initialize the tool runner with the path to your data directory.
        
        Args:
            data_dir: Path to the directory containing events.json, people.json, etc.
        """
        self.data_dir = data_dir
        self._events = None
        self._people = None
        self._groups = None
    
    def _load_events(self) -> list[dict]:
        """Lazy-load events data."""
        if self._events is None:
            events_file = f"{self.data_dir}/events.json"
            try:
                with open(events_file, 'r') as f:
                    self._events = json.load(f)
            except FileNotFoundError:
                self._events = []
        return self._events
    
    def _load_people(self) -> list[dict]:
        """Lazy-load people data."""
        if self._people is None:
            people_file = f"{self.data_dir}/people.json"
            try:
                with open(people_file, 'r') as f:
                    self._people = json.load(f)
            except FileNotFoundError:
                self._people = []
        return self._people
    
    def get_available_tools(self) -> list[dict]:
        """
        Returns tool descriptions that can be included in the LLM prompt.
        This teaches the LLM what tools it can call.
        """
        return [
            {
                "name": "get_upcoming_events",
                "description": "Get upcoming MCMP events within N days",
                "parameters": {"days": "int (default 14)", "event_type": "str (optional)"}
            },
            {
                "name": "find_person",
                "description": "Find a person at MCMP by name",
                "parameters": {"name": "str (required)"}
            },
            {
                "name": "search_by_topic",
                "description": "Search MCMP data by research topic",
                "parameters": {"topic": "str (required)"}
            },
            {
                "name": "get_reading_groups",
                "description": "List MCMP reading groups",
                "parameters": {"active_only": "bool (default True)"}
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Execute a tool and return the result as a string.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of tool arguments
        
        Returns:
            Formatted string result
        """
        from datetime import datetime, timedelta
        
        if tool_name == "get_upcoming_events":
            days = arguments.get("days", 14)
            event_type = arguments.get("event_type", "all")
            events = self._load_events()
            
            today = datetime.now()
            cutoff = today + timedelta(days=days)
            
            upcoming = []
            for event in events:
                try:
                    event_date = datetime.fromisoformat(event.get('date', ''))
                    if today <= event_date <= cutoff:
                        if event_type == "all" or event.get('type', '').lower() == event_type.lower():
                            upcoming.append(event)
                except (ValueError, TypeError):
                    continue
            
            if not upcoming:
                return f"No events found in the next {days} days."
            
            result = f"Upcoming events (next {days} days):\n"
            for event in sorted(upcoming, key=lambda x: x.get('date', ''))[:10]:
                result += f"- {event.get('title', 'Untitled')} | {event.get('date', 'TBA')} | {event.get('speaker', 'TBA')}\n"
            
            return result
        
        elif tool_name == "find_person":
            name = arguments.get("name", "").lower()
            people = self._load_people()
            
            matches = [p for p in people if name in p.get('name', '').lower()]
            
            if not matches:
                return f"No person found matching '{name}'."
            
            result = ""
            for person in matches[:3]:
                result += f"Name: {person.get('name')}\n"
                result += f"Role: {person.get('role', 'Not specified')}\n"
                result += f"Email: {person.get('email', 'Not available')}\n"
                if person.get('research_interests'):
                    result += f"Research: {', '.join(person.get('research_interests', []))}\n"
                result += "\n"
            
            return result
        
        elif tool_name == "search_by_topic":
            topic = arguments.get("topic", "").lower()
            events = self._load_events()
            people = self._load_people()
            
            related_events = [e for e in events if topic in f"{e.get('title', '')} {e.get('abstract', '')}".lower()]
            related_people = [p for p in people if topic in f"{p.get('name', '')} {' '.join(p.get('research_interests', []))}".lower()]
            
            result = f"Results for '{topic}':\n"
            
            if related_events:
                result += f"\nEvents ({len(related_events)}):\n"
                for e in related_events[:5]:
                    result += f"- {e.get('title', 'Untitled')}\n"
            
            if related_people:
                result += f"\nPeople ({len(related_people)}):\n"
                for p in related_people[:5]:
                    result += f"- {p.get('name', 'Unknown')}\n"
            
            if not related_events and not related_people:
                result = f"No results found for '{topic}'."
            
            return result
        
        return f"Unknown tool: {tool_name}"


def create_tool_aware_prompt(user_question: str, tool_runner: MCMPToolRunner) -> str:
    """
    Create a prompt that makes the LLM aware of available tools.
    
    The LLM will respond with tool calls in a parseable format.
    
    Args:
        user_question: The user's question
        tool_runner: MCMPToolRunner instance
    
    Returns:
        System prompt with tool instructions
    """
    tools = tool_runner.get_available_tools()
    
    tool_descriptions = "\n".join([
        f"- {t['name']}: {t['description']} (params: {t['parameters']})"
        for t in tools
    ])
    
    return f"""You are a helpful assistant for MCMP (Munich Center for Mathematical Philosophy).

You have access to these tools to query MCMP data:
{tool_descriptions}

To use a tool, respond with:
TOOL: tool_name
ARGS: {{"param": "value"}}

You can use multiple tools if needed. After getting tool results, provide a final answer.

If you don't need any tools, just answer directly.

User question: {user_question}"""


def parse_tool_calls(llm_response: str) -> list[tuple[str, dict]]:
    """
    Parse tool calls from LLM response.
    
    Args:
        llm_response: Raw LLM response text
    
    Returns:
        List of (tool_name, arguments) tuples
    """
    tool_calls = []
    lines = llm_response.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("TOOL:"):
            tool_name = line.replace("TOOL:", "").strip()
            args = {}
            
            # Look for ARGS on next line
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("ARGS:"):
                args_str = lines[i + 1].replace("ARGS:", "").strip()
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    pass
                i += 1
            
            tool_calls.append((tool_name, args))
        i += 1
    
    return tool_calls
```

### Putting It Together: Enhanced Engine

```python
# src/core/engine_enhanced.py
"""
Enhanced RAG engine combining Chain-of-Thought with MCP-style tools.
This is a drop-in enhancement for your existing engine.py
"""

from typing import Optional
import google.generativeai as genai  # Or your LLM client

from .mcp_integration import MCMPToolRunner, create_tool_aware_prompt, parse_tool_calls


class EnhancedRAGEngine:
    """
    Enhanced RAG engine that combines:
    1. Step-back prompting for better retrieval
    2. Tool-based structured data access
    3. Multi-step reasoning
    """
    
    def __init__(self, vector_store, llm_client, data_dir: str):
        """
        Initialize the enhanced engine.
        
        Args:
            vector_store: ChromaDB vector store instance
            llm_client: Configured LLM client (Gemini, etc.)
            data_dir: Path to data directory for MCP tools
        """
        self.vector_store = vector_store
        self.llm = llm_client
        self.tool_runner = MCMPToolRunner(data_dir)
    
    def _step_back_query(self, question: str) -> str:
        """Generate a step-back (more abstract) version of the question."""
        prompt = f"""Given this specific question about MCMP:
"{question}"

What is a more general question that would help provide context?
Respond with ONLY the general question."""
        
        response = self.llm.generate_content(prompt)
        return response.text.strip()
    
    def _retrieve_context(self, question: str, top_k: int = 5) -> list[str]:
        """
        Retrieve context using step-back prompting.
        
        Queries both the original question and a more abstract version.
        """
        # Original query
        original_results = self.vector_store.query(
            query_texts=[question], 
            n_results=top_k
        )
        
        # Step-back query
        abstract_question = self._step_back_query(question)
        abstract_results = self.vector_store.query(
            query_texts=[abstract_question], 
            n_results=top_k // 2
        )
        
        # Combine and deduplicate
        all_chunks = []
        seen = set()
        
        for doc in original_results['documents'][0] + abstract_results['documents'][0]:
            doc_hash = hash(doc[:100])
            if doc_hash not in seen:
                seen.add(doc_hash)
                all_chunks.append(doc)
        
        return all_chunks
    
    def answer(self, user_question: str, max_tool_iterations: int = 2) -> str:
        """
        Answer a user question using the enhanced RAG approach.
        
        This method:
        1. Retrieves relevant context using step-back prompting
        2. Offers the LLM structured tools for additional queries
        3. Iterates if the LLM needs more information
        
        Args:
            user_question: The user's question
            max_tool_iterations: Maximum tool call rounds
        
        Returns:
            Final answer string
        """
        # Step 1: Get initial context from vector store
        context_chunks = self._retrieve_context(user_question)
        context_text = "\n\n".join(context_chunks)
        
        # Step 2: Create tool-aware prompt
        tool_prompt = create_tool_aware_prompt(user_question, self.tool_runner)
        
        # Step 3: First LLM call - decide if tools are needed
        initial_prompt = f"""{tool_prompt}

I've already retrieved this context from the database:
---
{context_text[:3000]}
---

Based on this context, either:
1. Answer the question directly if you have enough information
2. Use tools to get more specific/structured information

Your response:"""
        
        response = self.llm.generate_content(initial_prompt)
        current_response = response.text
        
        # Step 4: Iteratively handle tool calls
        tool_results = []
        for iteration in range(max_tool_iterations):
            tool_calls = parse_tool_calls(current_response)
            
            if not tool_calls:
                # No tools requested, we're done
                break
            
            # Execute each tool
            for tool_name, args in tool_calls:
                result = self.tool_runner.execute_tool(tool_name, args)
                tool_results.append(f"[{tool_name}]: {result}")
            
            # Give results back to LLM
            followup_prompt = f"""You asked to use these tools, here are the results:

{chr(10).join(tool_results)}

Original question: {user_question}

Now provide your final answer. If you need more tools, request them. Otherwise, answer the question."""
            
            response = self.llm.generate_content(followup_prompt)
            current_response = response.text
        
        # Clean up response (remove any remaining tool syntax)
        final_answer = current_response
        if "TOOL:" in final_answer:
            # Extract just the natural language part
            lines = final_answer.split('\n')
            final_answer = '\n'.join(
                line for line in lines 
                if not line.strip().startswith(('TOOL:', 'ARGS:'))
            )
        
        return final_answer.strip()
```

---

## Quick Implementation Guide

### Minimal Effort (15 minutes)
Just add **query decomposition** to your existing `engine.py`:

```python
# In your existing answer function, replace the single retrieval with:

def answer(self, question: str) -> str:
    # Decompose the query
    queries = [question]
    decompose_prompt = f'Break this into 1-2 search queries: "{question}"\nReturn only queries, one per line.'
    decomp_response = self.llm.generate_content(decompose_prompt)
    queries.extend([q.strip() for q in decomp_response.text.split('\n') if q.strip()])
    
    # Retrieve for all queries
    all_chunks = []
    for q in queries[:3]:
        results = self.vector_store.query(query_texts=[q], n_results=3)
        all_chunks.extend(results['documents'][0])
    
    # Deduplicate and continue with your existing logic
    unique_chunks = list(dict.fromkeys(all_chunks))
    # ... rest of your existing code
```

### Medium Effort (1-2 hours)
Add **step-back prompting** + **self-ask loop** from the code above.

### Full Implementation (half day)
Add the **MCP server** for structured data access.

---

## Cost Comparison

| Strategy | Extra API Calls | Cost Increase |
|----------|-----------------|---------------|
| Query Decomposition | +1 small call | ~5-10% |
| Step-Back Prompting | +1 small call | ~5-10% |
| Self-Ask (2 iterations) | +2-4 calls | ~30-50% |
| MCP Tools (2 iterations) | +2-4 calls | ~30-50% |

**Recommendation**: Start with **Query Decomposition** or **Step-Back Prompting** - they give the best quality improvement for minimal cost increase.

---

## Expected Improvements

These strategies typically improve RAG performance by:

- **Recall**: 15-30% more relevant documents retrieved
- **Accuracy**: Fewer hallucinations due to better context
- **Completeness**: Better answers for multi-part questions
- **Specificity**: MCP tools give precise, structured answers

The key insight is that a single embedding query often misses relevant information. Breaking questions apart or asking for more abstract versions casts a wider net while keeping the LLM grounded in actual data.
