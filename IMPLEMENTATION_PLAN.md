# MCMP Chatbot Implementation Plan

Build a RAG-based chatbot for the Munich Center for Mathematical Philosophy (MCMP) that provides up-to-date information about its activities by scraping its website.

## User Review Required

> [!IMPORTANT]
> - **API Keys**: You will need to provide an OpenAI or Anthropic API key for embeddings and LLM responses.
> - **Scraping Frequency**: The chatbot will rely on a local cache/database. We should decide how often to refresh the data (e.g., daily or on-demand).

## Proposed Changes

### Project Structure & Setup
- Initialize the project with a structure similar to `local_nexus`:
  - `src/scrapers/`: Scraper logic.
  - `src/core/`: RAG pipeline, vector DB management, LLM integration.
  - `src/ui/`: Streamlit components.
  - `data/`: Local storage for the vector database and raw scraped data.

---

### Data Acquisition (Scraper)
- **[NEW] [scraper.py](file:///Users/ignacio/Documents/VS%20Code/GitHub%20Repositories/mcmp_chatbot/src/scrapers/mcmp_scraper.py)**: 
  - Functions to crawl `https://www.philosophie.lmu.de/mcmp/en/latest-news/events-overview/index.html`.
  - Extract event metadata: Title, Date, Speaker, Location, URL.
  - Visit each event URL to extract the full description.

---

### RAG Pipeline
- **[NEW] [vector_store.py](file:///Users/ignacio/Documents/VS%20Code/GitHub%20Repositories/mcmp_chatbot/src/core/vector_store.py)**:
  - Integration with `ChromaDB` or `LanceDB`.
  - Logic for chunking event descriptions and generating embeddings.
- **[NEW] [engine.py](file:///Users/ignacio/Documents/VS%20Code/GitHub%20Repositories/mcmp_chatbot/src/core/engine.py)**:
  - Query processing logic: Retrieve relevant events and generate a response using an LLM.

---

### Web Interface
- **[MODIFY] [app.py](file:///Users/ignacio/Documents/VS%20Code/GitHub%20Repositories/mcmp_chatbot/src/app.py)**:
  - Adapt the entry point from `local_nexus` to use the new RAG engine.
- **[NEW] [chat.py](file:///Users/ignacio/Documents/VS%20Code/GitHub%20Repositories/mcmp_chatbot/src/ui/chat_component.py)**:
  - Updated chat component with RAG integration.

## Verification Plan

### Automated Tests
- Run the scraper script and verify it produces a valid JSON/CSV of events:
  `python src/scrapers/mcmp_scraper.py --test`
- Test the vector store by indexing a sample event and querying it:
  `pytest tests/test_vector_store.py`

### Manual Verification
1.  **Scraping**: Verify that the database contains recent events from the MCMP website.
2.  **Chat**: Ask the chatbot about a specific upcoming talk (e.g., "Tell me about Carl Hoefer's talk on Jan 28").
3.  **Accuracy**: Cross-reference the chatbot's answer with the information on the website.
