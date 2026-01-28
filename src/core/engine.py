import os
from dotenv import load_dotenv
from src.core.vector_store import VectorStore
from src.core.graph_utils import GraphUtils
from src.utils.logger import log_info, log_error
import openai
from anthropic import Anthropic
from datetime import datetime

load_dotenv()

class RAGEngine:
    def __init__(self, provider="openai", api_key=None):
        self.vs = VectorStore()
        self.graph_utils = GraphUtils()
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
        
        for query in queries:
            results = self.vs.query(query, n_results=top_k)
            
            # VectorStore.query returns dictionary with lists
            # We need to handle potential empty results
            if not results['ids'] or not results['ids'][0]:
                continue

            for i, doc_id in enumerate(results['ids'][0]):
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_chunks.append({
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'source_query': query
                    })
        
        return all_chunks

    def generate_response(self, query):
        """Retrieves relevant events and generates a response using the selected LLM provider."""
        log_info(f"Generating response for query: {query}")
        
        # 1. Retrieve context
        # 1. Retrieve context with decomposition
        context_chunks = self.retrieve_with_decomposition(query)
        
        # Combine docs with their metadata
        formatted_context = []
        for chunk in context_chunks:
            source_url = chunk['metadata'].get('url', 'No URL available')
            formatted_entry = f"{chunk['text']}\nSource URL: {source_url}"
            formatted_context.append(formatted_entry)
            
        context_text = "\n\n---\n\n".join(formatted_context)
        
        context_text = "\n\n---\n\n".join(formatted_context)
        
        # 2. Retrieve graph context
        graph_data = self.graph_utils.get_subgraph(query)
        graph_context_text = self.graph_utils.to_natural_language(graph_data)
        if not graph_context_text:
            graph_context_text = "No specific institutional relationships found."
        
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        prompt = f"""You are the official Munich Center for Mathematical Philosophy (MCMP) Intelligence Assistant. 
        
Current Date: {current_date} 

Your goal is to serve as a comprehensive guide to the MCMP. You can answer questions about:
- **Research**: Ongoing projects, philosophy of AI/ML, logic, and philosophy of science.
- **People**: Faculty, fellows, and researchers.
- **Events**: Upcoming talks, workshops, and reading groups.
- **General Info**: History, aims, and institutional details.

### Guidelines:
1. **Context-First**: Use the provided context to answer. If the context contains details like speaker names, dates, locations, or abstracts, include them in your response.
2. **Handle Uncertainty**: If the provided context does not contain the answer, politely inform the user that you don't have that specific information yet. However, briefly mention what the MCMP is (a world-leading hub for formal philosophy) to remain helpful.
3. **Tone**: Be professional, scholarly, yet accessible.
4. **Citations & Links**: **ALWAYS** link back to the source using Markdown format `[Link Text](URL)`. If a URL is provided in the context, use it to create a clickable link in your answer.

---
### INSTITUTIONAL CONTEXT (GRAPH):
{graph_context_text}
---
### CONTEXT FROM MCMP WEBSITE:
{context_text}
---

### USER QUESTION:
{query}

### YOUR RESPONSE:"""

        try:
            if self.provider == "openai":
                client = openai.OpenAI(api_key=self.api_key)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )
                return response.choices[0].message.content
            elif self.provider == "anthropic":
                client = Anthropic(api_key=self.api_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            elif self.provider == "gemini":
                from google import genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=prompt
                )
                return response.text
        except Exception as e:
            log_error(f"Error generating response: {e}")
            return f"Error: {e}"

if __name__ == "__main__":
    engine = RAGEngine()
    # Mock run if API key is missing
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set. Retrieval test only:")
        vs = VectorStore()
        print(vs.query("Carl Hoefer"))
    else:
        print(engine.generate_response("Tell me about Carl Hoefer's talk."))
