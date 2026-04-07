import os
import json
from dotenv import load_dotenv
from src.core.personality import load_personality
from src.mcp.server import MCPServer
from src.utils.logger import log_info, log_error, log_latency
import openai
from anthropic import Anthropic
from datetime import datetime

load_dotenv()

class ChatEngine:
    """
    Core chatbot engine. Uses MCP structured tools to answer queries.
    All data access goes through the MCP tools:
    search_people, search_research, get_events, search_graph.
    """

    def __init__(self, provider="openai", api_key=None, use_mcp=True):
        self.provider = provider
        self.use_mcp = use_mcp

        # ── MCP server ──────────────────────────────────────────────────────
        self.mcp_server = MCPServer() if use_mcp else None

        # ── API key resolution ───────────────────────────────────────────────
        self.api_key = api_key
        if not self.api_key:
            key_map = {
                "openai":    "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "gemini":    "GEMINI_API_KEY",
            }
            self.api_key = os.getenv(key_map.get(provider, ""))

        if not self.api_key:
            msg = f"API Key for {provider} not found. Set it in .env or pass explicitly."
            log_error(msg)
            raise ValueError(msg)

        # ── Personality (cached once at startup) ─────────────────────────────
        self._personality = load_personality()

        # ── Pre-built tool list (static, no need to rebuild every call) ──────
        self._tool_defs = self.mcp_server.list_tools() if self.mcp_server else []
        self._tools_description_str = self._build_tools_description_str()

        # ── Gemini client (created once, reused across all calls) ────────────
        self._gemini_client = None
        if provider == "gemini":
            from google import genai
            self._gemini_client = genai.Client(api_key=self.api_key)
            log_info("Gemini client initialised at startup.")

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_tools_description_str(self) -> str:
        """Build the MCP tools section for the system prompt (done once at init)."""
        if not self._tool_defs:
            return ""
        lines = [
            "### AVAILABLE DATA TOOLS (MCP)",
            "You have permission to call these tools at any time. Do NOT ask the user for permission. Just call them.",
            "If context is partial or missing, call the relevant tool immediately to get full details.",
            "",
            "**TOOL SELECTION GUIDE** — pick the right tool for the query type:",
            "- User asks about a **person** (name, role, contact, publications, research) → `search_people(query='<name or keyword>')`, then optionally `search_graph(query='<name>')` for organizational context.",
            "- User asks about an **event, talk, or schedule** → `get_events(...)` with date range or keyword.",
            "- User asks about a **research area or field** (not a specific person) → `search_research(topic='<field>')`.",
            "- User asks about **organizational structure** (who leads what, supervisor, chair affiliation) → `search_graph(query='<name or unit>')`.",
            "- User asks about a **degree program, MA, Master, Bachelor, PhD, how to apply, application requirements, deadlines, or study programs** → `search_academic_offerings(offering_type='<master|bachelor|phd|learning_materials>')`. Use this FIRST for any question about studying at or applying to the MCMP.",
            "",
            "**FALLBACK CASCADE RULE — MANDATORY:**",
            "If a tool returns 0 results or an empty list, you MUST NOT give up and say 'I found nothing'.",
            "Instead, work through this cascade in order until you find results:",
            "  1. Try a **broader or simpler search term** with the same tool (e.g. 'machine learning' → 'learning', 'ML').",
            "  2. Try `search_people(query='<topic>')` — the topic may appear in a researcher's bio or interests even if no research area entry exists.",
            "  3. Try `grep_data(pattern='<keyword>', database='all')` — grep searches the full text of all records including bios and abstracts.",
            "  4. Only after exhausting all three steps above may you tell the user nothing was found — and if so, suggest related topics they could try.",
            "",
            "**QUERY EXTRACTION RULE**: Always extract only the relevant name or keyword for the query parameter.",
            "  ✓ User says 'tell me about a researcher named Landes' → query='Landes'",
            "  ✓ User says 'who works on probability' → query='probability'",
            "  ✗ Never pass the full user sentence as the query.",
            "",
            "**Tools:**",
        ]
        for t in self._tool_defs:
            lines.append(f"- `{t['name']}`: {t['description']}")
        lines.append("---")
        return "\n".join(lines)

    def _build_system_instruction(self) -> str:
        """Compose the full system instruction for each call (only dynamic part is the date)."""
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        return (
            f"{self._personality}\n\n"
            f"---\nCurrent Date: {current_date}\n---\n"
            f"{self._tools_description_str}\n"
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_response(self, query: str, use_mcp_tools: bool = False,
                          model_name: str = "gemini-2.0-flash",
                          chat_history: list = None,
                          status_callback=None) -> str:
        """
        Generate a response using the configured LLM provider.
        chat_history: list of dicts with 'role' ('user'/'assistant') and 'content' keys.
        status_callback: optional callable(tool_name, arguments) fired each time a tool is invoked.
        """
        log_info(f"Generating response. Query: '{query}' | Tools: {use_mcp_tools} | Model: {model_name}")

        with log_latency("build_system_instruction"):
            system_instruction = self._build_system_instruction()

        # ── Resolve tools for this call ──────────────────────────────────────
        with log_latency("build_tools"):
            tools = []
            if use_mcp_tools and self.mcp_server:
                if self.provider == "gemini":
                    # Use instrumented wrappers if a callback was provided so the
                    # UI can show which tool is being called in real time.
                    if status_callback:
                        tools = self.mcp_server.get_instrumented_tools(status_callback)
                    else:
                        tools = list(self.mcp_server.tools.values())
                elif self.provider == "openai":
                    tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": td["name"],
                                "description": td["description"],
                                "parameters": td["input_schema"],
                            },
                        }
                        for td in self._tool_defs
                    ]

        try:
            # ── OpenAI ───────────────────────────────────────────────────────
            if self.provider == "openai":
                client = openai.OpenAI(api_key=self.api_key)
                messages = [
                    {"role": "system", "content": system_instruction},
                ]
                if chat_history:
                    for msg in chat_history:
                        if msg.get("role") in ("user", "assistant"):
                            messages.append({"role": msg["role"], "content": msg["content"]})
                messages.append({"role": "user", "content": query})
                completion_args = {"model": "gpt-4o", "messages": messages, "temperature": 0}
                if tools:
                    completion_args["tools"] = tools

                with log_latency("llm_api_call"):
                    response = client.chat.completions.create(**completion_args)
                message = response.choices[0].message

                if message.tool_calls:
                    messages.append(message)
                    for tc in message.tool_calls:
                        fn   = tc.function.name
                        args = json.loads(tc.function.arguments)
                        log_info(f"Tool call: {fn}({args})")
                        result = self.mcp_server.call_tool(fn, args, status_callback=status_callback)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        })
                    with log_latency("llm_api_call_2"):
                        response = client.chat.completions.create(
                            model="gpt-4o", messages=messages, temperature=0
                        )
                    return response.choices[0].message.content
                return message.content

            # ── Anthropic ────────────────────────────────────────────────────
            elif self.provider == "anthropic":
                client = Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    system=system_instruction,
                    messages=[{"role": "user", "content": query}],
                )
                return response.content[0].text

            # ── Gemini ───────────────────────────────────────────────────────
            elif self.provider == "gemini":
                from google.genai import types

                with log_latency("gemini_chat_create"):
                    # Build history for multi-turn conversation
                    gemini_history = []
                    if chat_history:
                        for msg in chat_history:
                            role = msg.get("role")
                            content = msg.get("content", "")
                            if role == "user":
                                gemini_history.append(
                                    types.Content(role="user", parts=[types.Part.from_text(text=content)])
                                )
                            elif role == "assistant":
                                gemini_history.append(
                                    types.Content(role="model", parts=[types.Part.from_text(text=content)])
                                )
                    chat = self._gemini_client.chats.create(
                        model=model_name,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=tools,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                disable=False,
                                maximum_remote_calls=10,
                            ),
                        ),
                        history=gemini_history,
                    )

                with log_latency("llm_api_call"):
                    response = chat.send_message(query)
                return response.text

        except Exception as e:
            log_error(f"Error generating response: {e}")
            return f"Error: {e}"


if __name__ == "__main__":
    engine = ChatEngine(use_mcp=True, provider="gemini")
    print(engine.generate_response("List all upcoming events", use_mcp_tools=True))
