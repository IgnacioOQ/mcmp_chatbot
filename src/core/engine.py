import os
import json
from dotenv import load_dotenv
from src.core.graph_utils import GraphUtils
from src.core.personality import load_personality
from src.mcp.server import MCPServer
from src.utils.logger import log_info, log_error
import openai
from anthropic import Anthropic
from datetime import datetime

load_dotenv()

class ChatEngine:
    def __init__(self, provider="openai", api_key=None):
        self.graph_utils = GraphUtils()
        self.mcp_server = MCPServer()
        self.provider = provider
        
        # 1. Try passed key
        self.api_key = api_key
        
        # 2. Try environment variables if not passed
        if not self.api_key:
            if provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif provider == "anthropic":
                self.api_key = os.getenv("ANTHROPIC_API_KEY")
            elif provider == "gemini":
                self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            error_msg = f"API Key for {provider} not found. Please set it in .env or pass it explicitly."
            log_error(error_msg)
            raise ValueError(error_msg)

    def generate_response(self, query, model_name="gemini-2.0-flash", chat_history=None):
        """
        Generates a response using the configured LLM provider with MCP tools.
        """
        log_info(f"Generating response for query: {query}. Model: {model_name}")
        
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        
        # Load static personality from file
        personality = load_personality()

        # Compose system instruction: personality + date
        system_instruction = f"""{personality}

---
Current Date: {current_date}
---
"""
        
        # Get tool definitions and build text description for the System Prompt
        tool_defs = self.mcp_server.list_tools()
        
        tools_description_str = "### AVAILABLE DATA TOOLS (MCP):\n"
        tools_description_str += "You have access to the following tools to fetch real-time data.\n"
        tools_description_str += "IMPORTANT: You have permission to use these tools. Do NOT ask the user if they want you to check. Just check.\n"
        tools_description_str += "Use these tools to answer ANY question about MCMP people, events, research, or institutional structure:\n"
        for t in tool_defs:
            tools_description_str += f"- `{t['name']}`: {t['description']}\n"
        tools_description_str += "---\n"
        
        # Prepare provider-specific tool objects
        tools = []
        if self.provider == "gemini":
            tools = list(self.mcp_server.tools.values())
        elif self.provider == "openai":
            for tool_def in tool_defs:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_def["name"],
                        "description": tool_def["description"],
                        "parameters": tool_def["input_schema"]
                    }
                })

        try:
            final_system_instruction = f"""{system_instruction}
{tools_description_str}
"""

            if self.provider == "openai":
                client = openai.OpenAI(api_key=self.api_key)
                
                messages = [
                    {"role": "system", "content": final_system_instruction},
                ]
                if chat_history:
                    for msg in chat_history:
                        if msg["role"] in ("user", "assistant"):
                            messages.append({"role": msg["role"], "content": msg["content"]})
                messages.append({"role": "user", "content": query})
                
                # First Call
                completion_args = {
                    "model": "gpt-4o",
                    "messages": messages,
                    "temperature": 0,
                    "tools": tools
                }

                response = client.chat.completions.create(**completion_args)
                message = response.choices[0].message
                
                # Check for tool calls
                if message.tool_calls:
                    messages.append(message) # Add assistant's tool-call message
                    
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        log_info(f"Executing Tool: {function_name} with args {arguments}")
                        
                        result = self.mcp_server.call_tool(function_name, arguments)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result)
                        })
                    
                    # Second Call (with tool results)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0
                    )
                    return response.choices[0].message.content
                else:
                    return message.content

            elif self.provider == "anthropic":
                client = Anthropic(api_key=self.api_key)
                anthropic_messages = []
                if chat_history:
                    for msg in chat_history:
                        if msg["role"] in ("user", "assistant"):
                            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})
                anthropic_messages.append({"role": "user", "content": query})
                response = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    system=final_system_instruction,
                    messages=anthropic_messages
                )
                return response.content[0].text

            elif self.provider == "gemini":
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.api_key)

                # Convert chat history to Gemini format
                gemini_history = []
                if chat_history:
                    for msg in chat_history:
                        if msg["role"] == "user":
                            gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
                        elif msg["role"] == "assistant":
                            gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))

                chat = client.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction,
                        tools=tools,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=False,
                            maximum_remote_calls=5
                        )
                    ),
                    history=gemini_history
                )

                response = chat.send_message(query)
                return response.text

        except Exception as e:
            log_error(f"Error generating response: {e}")
            return f"Error: {e}"

if __name__ == "__main__":
    engine = ChatEngine()
    if not os.getenv("OPENAI_API_KEY"):
       pass
    else:
        print(engine.generate_response("List all upcoming events"))
