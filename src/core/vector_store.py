import chromadb
from chromadb.utils import embedding_functions
import json
import os
import hashlib
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

    def _generate_id(self, url):
        """Generates a stable ID based on the URL."""
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def add_events(self):
        """Indexes all scraped data (events, people, research) into ChromaDB with persistence."""
        
        # Load all data sources
        data_files = {
            "event": "data/raw_events.json",
            "person": "data/people.json",
            "research": "data/research.json",
            "general": "data/general.json",
            "knowledge": "data/knowledge.json"
        }
        
        ids = []
        used_ids = set()
        documents = []
        metadatas = []

        for type_label, filepath in data_files.items():
            if not os.path.exists(filepath):
                continue
                
            with open(filepath, 'r', encoding='utf-8') as f:
                items = json.load(f)
            
            for item in items:
                url = item.get('url', '')
                if not url:
                    continue
                    
                # Stable ID
                base_id = self._generate_id(url)
                doc_id = base_id
                
                # Handle duplicates in the current batch
                counter = 1
                while doc_id in used_ids:
                    doc_id = f"{base_id}_{counter}"
                    counter += 1
                
                ids.append(doc_id)
                used_ids.add(doc_id)
                
                # Content formatting based on type
                if type_label == "event":
                    content = f"Event: {item['title']}\nDescription: {item.get('description', '')}"
                elif type_label == "person":
                    content = f"Person: {item['name']}\nProfile: {url}"
                elif type_label == "research":
                    content = f"Research Project: {item['title']}\nDescription: {item.get('description', '')}"
                elif type_label == "general":
                    content = f"{item['title']}\n{item.get('description', '')}"
                elif type_label == "knowledge":
                    content = f"Concept: {item['title']}\n{item.get('description', '')}"
                
                documents.append(content)
                
                # Metadata
                meta = {
                    "type": type_label,
                    "title": item.get('title') or item.get('name'),
                    "url": url,
                    "scraped_at": item.get('scraped_at', '')
                }
                # Flatten extra metadata
                if 'metadata' in item:
                    for k, v in item['metadata'].items():
                        meta[f"meta_{k}"] = str(v)
                
                metadatas.append(meta)

        if ids:
            # upsert updates existing IDs and inserts new ones
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            log_info(f"Upserted {len(ids)} items into vector store (History preserved).")

    def query(self, query_texts, n_results=3):
        """Queries the vector store for relevant events. Can accept a single string or a list of strings."""
        if isinstance(query_texts, str):
            query_texts = [query_texts]

        results = self.collection.query(
            query_texts=query_texts,
            n_results=n_results
        )
        return results

if __name__ == "__main__":
    vs = VectorStore()
    vs.add_events()
    # Quick test query
    results = vs.query("Logic and Mathematics")
    print(f"Query Results: {json.dumps(results, indent=2)}")
