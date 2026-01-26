import chromadb
from chromadb.utils import embedding_functions
import json
import os
from src.utils.logger import log_info, log_error

class VectorStore:
    def __init__(self, db_path="data/vectordb", collection_name="mcmp_events"):
        self.client = chromadb.PersistentClient(path=db_path)
        # Using default embedding function (sentence-transformers/all-MiniLM-L6-v2)
        # For production, we might want to use OpenAI or local high-quality models
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.ef
        )

    def add_events(self, events_json_path="data/raw_events.json"):
        """Indexes events from a JSON file into ChromaDB."""
        if not os.path.exists(events_json_path):
            log_error(f"JSON file not found: {events_json_path}")
            return

        with open(events_json_path, 'r', encoding='utf-8') as f:
            events = json.load(f)

        ids = []
        documents = []
        metadatas = []

        for i, event in enumerate(events):
            # Create a unique ID based on URL or index
            event_id = str(i)
            ids.append(event_id)
            
            # Combine title and description for indexing
            doc_content = f"Title: {event['title']}\n\nDescription: {event.get('description', 'No description available')}"
            documents.append(doc_content)
            
            # Store original URL and metadata for retrieval
            metadata = {
                "title": event['title'],
                "url": event['url'],
                "scraped_at": event['scraped_at']
            }
            # Add event-specific metadata if available
            if 'metadata' in event:
                for k, v in event['metadata'].items():
                    metadata[f"meta_{k.replace(' ', '_')}"] = str(v)
            
            metadatas.append(metadata)

        if ids:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            log_info(f"Indexed {len(ids)} events into vector store.")

    def query(self, text, n_results=3):
        """Queries the vector store for relevant events."""
        results = self.collection.query(
            query_texts=[text],
            n_results=n_results
        )
        return results

if __name__ == "__main__":
    vs = VectorStore()
    vs.add_events()
    # Quick test query
    results = vs.query("Logic and Mathematics")
    print(f"Query Results: {json.dumps(results, indent=2)}")
