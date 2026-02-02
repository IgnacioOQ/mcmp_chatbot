import os
import functools
import json
from dotenv import load_dotenv
from src.core.vector_store import VectorStore
from src.core.graph_utils import GraphUtils
from src.core.personality import load_personality
from src.mcp.server import MCPServer
from src.utils.logger import log_info, log_error
import openai
from anthropic import Anthropic
from datetime import datetime

load_dotenv()

class RAGEngine:
    def __init__(self, provider="openai", api_key=None, use_mcp=True):
        self.vs = VectorStore()
        self.graph_utils = GraphUtils()
        self.provider = provider
        self.use_mcp = use_mcp
        
        if self.use_mcp:
            self.mcp_server = MCPServer()
        else:
            self.mcp_server = None
        
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

    @functools.lru_cache(maxsize=128)
    def decompose_query(self, user_question):
        """
        Decomposes a complex question into simpler sub-queries.
        """
        decomposition_prompt = f"""Given this question about MCMP (Munich Center for Mathematical Philosophy):
"{user_question}"

Break it into 1-3 simple search queries that would help find relevant information.
Return ONLY the queries, one per line, no numbering or bullets.
If the question is already simple, just return it as-is."""

        try:
            if self.provider == "gemini":
                from google import genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=decomposition_prompt
                )
                text = response.text
            elif self.provider == "openai":
                client = openai.OpenAI(api_key=self.api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo", # Use cheaper model for decomposition
                    messages=[{"role": "user", "content": decomposition_prompt}],
                    temperature=0
                )
                text = response.choices[0].message.content
            elif self.provider == "anthropic":
                client = Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model="claude-3-haiku-20240307", # Use cheaper model
                    max_tokens=200,
                    messages=[{"role": "user", "content": decomposition_prompt}]
                )
                text = response.content[0].text
            else:
                return [user_question]

            queries = [q.strip() for q in text.strip().split('\n') if q.strip()]
            # Ensure original is included if list is empty or logical
            if user_question not in queries:
                queries.insert(0, user_question)
            
            return queries[:4]

        except Exception as e:
            log_error(f"Error in decomposition: {e}")
            return [user_question]

    def retrieve_with_decomposition(self, user_question, top_k=3):
        """
        Retrieve relevant chunks using query decomposition.
        """
        queries = self.decompose_query(user_question)
        log_info(f"Decomposed queries: {queries}")
        
        all_chunks = []
        seen_ids = set()
        
        if not queries:
            return []

        results = self.vs.query(queries, n_results=top_k)

        # Iterate over each query's results
        for q_idx, query_ids in enumerate(results['ids']):
            if not query_ids:
                continue

            query_text = queries[q_idx]

            for i, doc_id in enumerate(query_ids):
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_chunks.append({
                        'text': results['documents'][q_idx][i],
                        'metadata': results['metadatas'][q_idx][i] if results['metadatas'] else {},
                        'source_query': query_text
                    })
        
        return all_chunks

    def generate_response(self, query, use_mcp_tools=False, model_name="gemini-2.0-flash"):
        """
        Generates a response using the configured LLM provider.
        """
        log_info(f"Generating response for query: {query}. Tools enabled: {use_mcp_tools}. Model: {model_name}")
        
        # 1. Retrieve context with decomposition
        context_chunks = self.retrieve_with_decomposition(query)
        
        formatted_context = []
        for chunk in context_chunks:
            meta = chunk['metadata']
            source_url = meta.get('url', 'No URL available')
            title = meta.get('title', 'Untitled')
            
            # Extract rich fields if available
            description = meta.get('meta_description', '')
            abstract = meta.get('meta_abstract', '')
            role = meta.get('meta_role', '')
            
            # Construct a rich context entry
            formatted_entry = f"Title: {title}\nSource URL: {source_url}"
            
            if role:
                 formatted_entry += f"\nRole: {role}"
            
            # Add content text (which is usually a summary or full text depending on ingestion)
            formatted_entry += f"\nContent: {chunk['text']}"
            
            # Append description/abstract if not already in text (simple heuristic) or just append for completeness
            if description and len(description) > 50:
                formatted_entry += f"\nDescription: {description}"
            if abstract and len(abstract) > 50:
                formatted_entry += f"\nAbstract: {abstract}"
                
            formatted_context.append(formatted_entry)
            
        context_text = "\n\n---\n\n".join(formatted_context)
        
        # 2. Retrieve graph context
        graph_data = self.graph_utils.get_subgraph(query)
        graph_context_text = self.graph_utils.to_natural_language(graph_data)
        if not graph_context_text:
            graph_context_text = "No specific institutional relationships found."
        
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        
        # Load static personality from file
        personality = load_personality()

        # Compose system instruction: static personality + dynamic context
        system_instruction = f"""{personality}

---
Current Date: {current_date}
---
### INSTITUTIONAL CONTEXT (GRAPH):
{graph_context_text}
---
### CONTEXT FROM MCMP WEBSITE:
{context_text}
---
"""
        
        # Prepare tools if enabled and available
        tools = []
        tools_description_str = ""

        if use_mcp_tools and self.mcp_server:
            # 1. Get tool definitions
            tool_defs = self.mcp_server.list_tools()
            
            # 2. Build text description for the System Prompt
            tools_description_str = "### AVAILABLE DATA TOOLS (MCP):\n"
            tools_description_str += "You have access to the following tools to fetch real-time data.\n"
            tools_description_str += "IMPORTANT: You have permission to use these tools. Do NOT ask the user if they want you to check. Just check.\n"
            tools_description_str += "If the text context is insufficient OR provides only partial information (like a title without an abstract), proceed IMMEDIATELY to calling the relevant tool to get the full details:\n"
            for t in tool_defs:
                tools_description_str += f"- `{t['name']}`: {t['description']}\n"
            tools_description_str += "---\n"
            
            # 3. Prepare provider-specific tool objects
            if self.provider == "gemini":
                tools = list(self.mcp_server.tools.values())
            elif self.provider == "openai":
                tools = []
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
            # Update system instruction to include tools description
            final_system_instruction = f"""{system_instruction}
{tools_description_str}
"""

            if self.provider == "openai":
                client = openai.OpenAI(api_key=self.api_key)
                
                messages = [
                    {"role": "system", "content": final_system_instruction},
                    {"role": "user", "content": query}
                ]
                
                # First Call
                completion_args = {
                    "model": "gpt-4o",
                    "messages": messages,
                    "temperature": 0
                }
                if tools:
                    completion_args["tools"] = tools

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
                # Basic implementation without tools for now to keep it safe
                client = Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    system=final_system_instruction,
                    messages=[{"role": "user", "content": query}]
                )
                return response.content[0].text

            elif self.provider == "gemini":
                from google import genai
                from google.genai import types
                
                client = genai.Client(api_key=self.api_key)
                
                config = {}
                if tools:
                    config['tools'] = tools
                
                # We need to construct the chat history manually to include system instruction context
                # Gemini doesn't support 'system' role in chat history often, usually config.
                # simpler to just prepend context to user message or use system_instruction argument
                
                # Note: 'gemini-flash-latest' might accept system_instruction in config or init.
                # Let's try passing it in config if possible, or contents.
                
                # Actually newer genai client supports system_instruction='...'
                
                chat = client.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction,
                        tools=tools,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=False,
                            maximum_remote_calls=3
                        )
                    )
                )
                
                response = chat.send_message(query)
                return response.text

        except Exception as e:
            log_error(f"Error generating response: {e}")
            return f"Error: {e}"

if __name__ == "__main__":
    engine = RAGEngine(use_mcp=True)
    # Mock run if API key is missing
    if not os.getenv("OPENAI_API_KEY"):
       pass
    else:
        print(engine.generate_response("List all upcoming events", use_mcp_tools=True))
