# MCMP Chatbot

- status: active
- context_dependencies: {"agents": "AGENTS.md", "conventions": "docs/MD_CONVENTIONS.md"}

<!-- content -->

A RAG-based (Retrieval-Augmented Generation) chatbot for the **Munich Center for Mathematical Philosophy (MCMP)**. This application scrapes the MCMP website for the latest events, people, and research, and uses an LLM (Google Gemini, OpenAI, or Anthropic) to answer user queries about the center's activities.

The application is built with **Streamlit** for the frontend, uses **ChromaDB** for vector storage, and integrates with **Google Sheets** for cloud-based feedback collection.

## Features

- **Activity QA**: Ask about upcoming talks, reading groups, and events.
- **Automated Scraping**: Keeps data fresh by scraping the MCMP website.
- **Hybrid Search**: Combines semantic vector search with structured metadata filtering (e.g., filter by year, role, or funding).
- **RAG Architecture**: Uses vector embeddings to retrieve relevant context for accurate answers.
- **Cloud Database (Feedback)**: User feedback is automatically saved to a Google Sheet for persistent, cloud-based storage (with a local JSON fallback).
- **Multi-LLM Support**: Configured to work seamlessly with **Google Gemini**, but also supports OpenAI and Anthropic.
- **Smart Retrieval (Query Decomposition)**: automatically breaks down complex multi-part questions into simpler sub-queries for more complete answers.
- **Institutional Graph**: Uses a graph-based layer (`data/graph`) to understand organizational structure (Chairs, Leadership) and relationships between people.
- **Agentic Workflow**: Follows the `AGENTS.md` and `docs/MD_CONVENTIONS.md` protocols for AI-assisted development.

## Performance Optimization
- **Vector Search**: The retrieval engine uses **batch querying** to minimize latency. By sending all decomposed sub-queries to ChromaDB in a single parallel batch request, we achieved an **~82% reduction in retrieval time** (from ~0.43s to ~0.07s per query set).

## RAG Architecture Explained

This project is a definitive implementation of **Retrieval-Augmented Generation (RAG)**.

1.  **Retrieval**: The system uses `src/scrapers` to fetch data from the MCMP website, chunks it, and stores embeddings in `ChromaDB`. When a user asks a question, the system *retrieves* the most relevant chunks.
2.  **Augmentation**: These chunks are passed as context to the LLM (Gemini) via `src/core/engine.py`.
3.  **Generation**: The LLM *generates* a response based on the augmented prompt, ensuring accuracy grounded in the retrieved data.

> [!NOTE]
> For a general definition of RAG, see [data/WHAT_IS_RAG.md](data/WHAT_IS_RAG.md).

### Why Embeddings? (vs. just JSON)
While the system stores data in JSON files (raw material), it uses **Embeddings** as the search mechanism.
- **JSONs**: Store the text.
- **Embeddings**: Convert that text into vectors (lists of numbers) using a small LLM (Sentence Transformers).
This allows the system to find relevant information based on *meaning* (semantic search) rather than just keyword matching.
This allows the system to find relevant information based on *meaning* (semantic search) rather than just keyword matching.

### Advanced: Query Decomposition
For complex questions (e.g., *"Who is Mario Hubert and what is his talk about?"*), a single search often fails to find all necessary context. This project implements **Query Decomposition**:
1.  **Decompose**: The LLM breaks the user's complex question into distinct sub-queries (e.g., *"Who is Mario Hubert?"* and *"What is Mario Hubert's talk?"*).
2.  **Parallel Retrieval**: The system executes searches for *each* sub-query independently.
3.  **Synthesis**: All retrieved context chunks are combined and deduplicated before generating the final answer.

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd mcmp_chatbot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Secrets**:
   Create a `.streamlit/secrets.toml` file with your API keys.

   **For Google Gemini (Recommended):**
   - Get your API key from [Google AI Studio](https://aistudio.google.com/).
   ```toml
   GEMINI_API_KEY = "your-google-gemini-key"
   ```
   > [!NOTE]
   > The `GEMINI_API_KEY` determines where the LLM usage is billed. This is often a different Google Cloud project (e.g., `gen-lang-client...`) than the Service Account used for Sheets. To consolidate billing, link your API key to the `mcmp-chatbot` project in Google AI Studio.

   **For Cloud Feedback (Google Sheets):**
   - Create a project in [Google Cloud Console](https://console.cloud.google.com/).
   - Enable the [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com) and [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com).
   - Create a Service Account and download the JSON key.
   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key = "..."
   client_email = "..."
   # ... (other standard GCP credentials)
   sheet_name = "MCMP Feedback"
   ```

4. **Run the Application**:
   ```bash
   streamlit run app.py
   ```

## Data Maintenance
To keep the chatbot up to date with the latest MCMP events and personnel, run the update protocol:

```bash
python scripts/update_dataset.py
```
This script will:
1.  Scrape the MCMP website (Events, People, Research).
2.  Update JSON datasets (`data/*.json`).
3.  **Enrich Metadata**: Run internal utilities to extract structured metadata (dates, roles) from text descriptions.
4.  Rebuild the Institutional Graph (`data/graph/mcmp_graph.md` and `mcmp_jgraph.json`).

## Technical Architecture

### 1. Frontend: Streamlit
The user interface is built entirely in **Streamlit**, providing a clean, responsive chat interface. It handles user sessions, admin access (password protected), and feedback forms directly in the browser.

### 2. AI Engine: Google Gemini
The core logic (`src/core/engine.py`) connects to the **Gemini API** (or others) to generate responses. It prompts the model with retrieved context from the vector store to ensure accuracy and minimize hallucinations.

### 3. Data Storage
- **Vector Database**: Scraped content is chunked and embedded into a local **ChromaDB** instance (`data/vectordb`) for fast semantic retrieval.
- **Markdown Graph**: Institutional relationships are stored in `data/graph/mcmp_graph.md` and parsed by `src/core/graph_utils.py` for context injection.
- **Cloud Feedback**: User feedback is pushed to **Google Sheets** via the Google Drive API, acting as a cloud database for ongoing user data collection.

### 4. Data Model & Relationships
The system connects four key data types to answer complex questions:
1.  **People** (`data/people.json`): Raw profiles of researchers, including their bio, contact info, and roles.
2.  **Research** (`data/research.json`): Descriptions of projects and research areas.
3.  **Events** (`data/raw_events.json`): Upcoming talks and workshops.
4.  **Institutional Graph** (`data/graph/mcmp_graph.md`): A knowledge graph that links **People** to **Organizational Units** (Chairs) and defines hierarchy (e.g., who leads a chair, who supervises whom). 

**How they interact:**
- When a user asks "Who works at the Chair of Philosophy of Science?", the **Graph** identifies the Chair entity and its `affiliated_with` edges.
- The system then retrieves detailed profiles from **People** data.
- If the user asks "What does Ignacio Ojea research?", the system checks his **People** profile and relates it to relevant **Research** projects.

## Project Structure

```
mcmp_chatbot/
├── app.py                # Main Streamlit application entry point
├── src/
│   ├── core/             # RAG engine (Gemini) and Vector Store (Chroma)
│   ├── scrapers/         # Scrapers for MCMP website
│   └── utils/            # Helper functions (logging, etc.)
├── data/                 # Local data storage (JSONs, Vector DB)
├── docs/                 # Project documentation and proposals
│   ├── rag_improvements.md
│   ├── HOUSEKEEPING.md   # Maintenance protocols
│   └── MD_CONVENTIONS.md # Markdown conventions
├── AGENTS.md             # Guidelines for AI Agents
└── requirements.txt      # Python dependencies
```

## Agentic Workflow

This project uses a structured workflow for AI agents.
- **AGENTS.md**: Read this first if you are an AI assistant.
- **docs/MD_CONVENTIONS.md**: Defines the schema for Markdown files and task management.
