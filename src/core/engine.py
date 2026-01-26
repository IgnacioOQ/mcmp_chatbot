import os
from dotenv import load_dotenv
from src.core.vector_store import VectorStore
from src.utils.logger import log_info, log_error
import openai
from anthropic import Anthropic

load_dotenv()

class RAGEngine:
    def __init__(self, provider="openai"):
        self.vs = VectorStore()
        self.provider = provider
        if provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            log_error(f"API Key for {provider} not found in environment variables.")

    def generate_response(self, query):
        """Retrieves relevant events and generates a response using the selected LLM provider."""
        log_info(f"Generating response for query: {query}")
        
        # 1. Retrieve context
        results = self.vs.query(query, n_results=3)
        context_docs = results['documents'][0]
        context_metadatas = results['metadatas'][0]
        
        context_text = "\n\n---\n\n".join(context_docs)
        
        prompt = f"""You are a helpful assistant for the Munich Center for Mathematical Philosophy (MCMP). 
Use the following pieces of context about upcoming activities and events to answer the user's question. 
If you don't know the answer based on the context, just say that you don't know, don't try to make up an answer.

CONTEXT:
{context_text}

USER QUESTION:
{query}

ANSWER:"""

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
