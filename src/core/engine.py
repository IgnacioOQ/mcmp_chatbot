import os
from dotenv import load_dotenv
from src.core.vector_store import VectorStore
from src.utils.logger import log_info, log_error
import openai
from anthropic import Anthropic

load_dotenv()

class RAGEngine:
    def __init__(self, provider="openai", api_key=None):
        self.vs = VectorStore()
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

    def generate_response(self, query):
        """Retrieves relevant events and generates a response using the selected LLM provider."""
        log_info(f"Generating response for query: {query}")
        
        # 1. Retrieve context
        results = self.vs.query(query, n_results=3)
        context_docs = results['documents'][0]
        context_metadatas = results['metadatas'][0]
        
        # Combine docs with their metadata (specifically URL)
        formatted_context = []
        for doc, meta in zip(context_docs, context_metadatas):
            source_url = meta.get('url', 'No URL available')
            formatted_entry = f"{doc}\nSource URL: {source_url}"
            formatted_context.append(formatted_entry)
            
        context_text = "\n\n---\n\n".join(formatted_context)
        
        prompt = f"""You are the official Munich Center for Mathematical Philosophy (MCMP) Intelligence Assistant. 

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
