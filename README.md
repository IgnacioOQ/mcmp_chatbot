# MCMP Chatbot

- status: active
- context_dependencies: {"agents": "AGENTS.md", "conventions": "docs/MD_CONVENTIONS.md"}

<!-- content -->

A RAG-based (Retrieval-Augmented Generation) chatbot for the **Munich Center for Mathematical Philosophy (MCMP)**. This application scrapes the MCMP website for the latest events, people, and research, and uses an LLM (Google Gemini, OpenAI, or Anthropic) to answer user queries about the center's activities.

The application is built with **Streamlit** for the frontend, uses **ChromaDB** for vector storage, and integrates with **Google Sheets** for cloud-based feedback collection.

## Features

- **Activity QA**: Ask about upcoming talks, reading groups, and events.
- **Automated Scraping**: Keeps data fresh by scraping the MCMP website.
- **Rich Metadata Extraction**: Automatically extracts detailed profile information including emails, office locations, hierarchical roles, and publication lists.
- **Hybrid Search**: Combines semantic vector search with structured metadata filtering (e.g., filter by year, role, or funding).
- **RAG Architecture**: Uses vector embeddings to retrieve relevant context for accurate answers.
- **Cloud Database (Feedback)**: User feedback is automatically saved to a Google Sheet for persistent, cloud-based storage (with a local JSON fallback).
- **Multi-LLM Support**: Configured to work seamlessly with **Google Gemini**, but also supports OpenAI and Anthropic.
- **Smart Retrieval (Query Decomposition)**: automatically breaks down complex multi-part questions into simpler sub-queries for more complete answers.
- **Institutional Graph**: Uses a graph-based layer (`data/graph`) to understand organizational structure (Chairs, Leadership) while linking people to hierarchical **Research Topics**.
- **Structured Data Tools (MCP)**: Implements an in-process Model Context Protocol (MCP) server that exposes `people.json`, `research.json`, and `raw_events.json` as structured tools. This allows the LLM to perform precise queries (e.g., "List all events next week", "Who researches Logic?") rather than relying solely on semantic retrieval.
- **Configurable Personality (Leopold)**: The chatbot's personality is defined in `prompts/personality.md`, separating tone and identity from code. Edit the file to adjust behavior without touching the engine.
- **Agentic Workflow**: Follows the `AGENTS.md` and `docs/MD_CONVENTIONS.md` protocols for AI-assisted development.

## Performance Optimization
- **Vector Search**: The retrieval engine uses **batch querying** to minimize latency. By sending all decomposed sub-queries to ChromaDB in a single parallel batch request, we achieved an **~82% reduction in retrieval time** (from ~0.43s to ~0.07s per query set).

## RAG Architecture Explained

This project is a definitive implementation of **Retrieval-Augmented Generation (RAG)**.

1.  **Retrieval**: The system uses `src/scrapers` to fetch data from the MCMP website, chunks it, and stores embeddings in `ChromaDB`. When a user asks a question, the system *retrieves* the most relevant chunks.
2.  **Augmentation**: These chunks are passed as context to the LLM (Gemini) via `src/core/engine.py`.
3.  **Generation**: The LLM *generates* a response based on the augmented prompt, ensuring accuracy grounded in the retrieved data.



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

### 5. MCP Integration (Structured Data)
To handle specific queries that require structured data access (e.g., "Which events are happening between date X and Y?"), the system implements a lightweight **MCP Server** (`src/mcp/`).
- **Tools**: Exposes Python functions (`search_people`, `search_research`, `get_events`) as tools to the LLM.
- **Hybrid Execution**: The RAG engine first retrieves semantic context, then offers these tools to the LLM. If the LLM determines it needs precise data, it calls the tool, and the result is fed back for the final answer.
- **Toggle**: This feature is optional and can be enabled/disabled via the Streamlit sidebar to manage latency and costs.

### 4. Data Model & Relationships
The system connects four key data types to answer complex questions:
1.  **People** (`data/people.json`): Comprehensive profiles including bios, contact details (email, phone, office), organizational roles, and selected publications.
2.  **Research** (`data/research.json`): Hierarchical structure of research areas (e.g., Logic, Philosophy of Science) and their subtopics, with automated linking to people.
3.  **Events** (`data/raw_events.json`): Upcoming talks and workshops.
4.  **Institutional Graph** (`data/graph/mcmp_graph.md`): A knowledge graph that links **People** to **Organizational Units** (Chairs) and defines hierarchy (e.g., who leads a chair, who supervises whom). 


**How they interact:**
- When a user asks "Who works at the Chair of Philosophy of Science?", the **Graph** identifies the Chair entity and its `affiliated_with` edges.
- The system then retrieves detailed profiles from **People** data.
- If the user asks "What does Ignacio Ojea research?", the system checks his **People** profile, which is now automatically linked to relevant **Research Topics** (e.g., "Philosophy of Science") and specific projects.

## Query Processing Pipeline

This diagram illustrates how the system combines **RAG (Text)**, **Graph (Relationships)**, and **MCP (Structured Data)** to answer a user query.

```mermaid
graph TD
    UserQuery[User Query] --> Decompose[Query Decomposition]
    
    subgraph "Phase 1: Retrieval (RAG)"
        Decompose -->|Sub-queries| VectorDB[(ChromaDB)]
        VectorDB -->|Retrieved Chunks| ContextAgg{Context Aggregator}
        UserQuery -->|Direct Query| GraphDB[(Institutional Graph)]
        GraphDB -->|Graph Relationships| ContextAgg
    end
    
    subgraph "Phase 2: Generation & Tool Use (MCP)"
        ContextAgg -->|System Instruction| LLM[LLM (Gemini/OpenAI)]
        UserQuery --> LLM
        
        Tools[MCP Tools] -->|Defines: search_people, get_events| LLM
        
        LLM -- "Needs Structured Data?" --> ToolCall{Decision}
        ToolCall -- Yes --> ExecuteTool[Execute Tool]
        ExecuteTool -->|Query JSONs| JsonDB[(Data JSONs)]
        JsonDB -->|Structured Result| LLM
        ToolCall -- No/Done --> GenerateAnswer[Generate Answer]
    end
    
    GenerateAnswer --> FinalResponse[Final Response]

    style VectorDB fill:#e1f5fe,stroke:#01579b
    style JsonDB fill:#e8f5e9,stroke:#1b5e20
    style LLM fill:#fff3e0,stroke:#e65100
    style GraphDB fill:#f3e5f5,stroke:#4a148c
```

### Explanation of the Flow
1.  **Decomposition**: The complex user query is broken down into simpler sub-queries.
2.  **Hybrid Retrieval**:
    *   **Vector Search**: Finds relevant text chunks from the scraped website content (Vector DB).
    *   **Graph Search**: Identifies institutional relationships (leads, supervises, member of).
3.  **Context Construction**: The retrieved text and graph data are combined into a rich **System Instruction**.
4.  **LLM Execution with Tools**:
    *   The LLM receives the prompt and a list of available **MCP Tools** (e.g., `search_people`, `get_events`).
    *   It evaluates if the retrieved text context is sufficient.
    *   **Scenario A (Context Sufficient)**: The LLM answers directly using the RAG data.
    *   **Scenario B (Needs Structured Data)**: The LLM calls a tool (e.g., "Get events for next week"). The system executes this against the **JSON Database** and feeds the precise result back to the LLM.

5.  **Final Answer**: The LLM synthesizes the RAG context, Graph context, and Tool outputs into the final response.

### 3. Example Walkthrough

**Query:** *"What is Hannes Leitgeb working on and what are his upcoming events?"*

1.  **Decomposition**:
    *   Sub-query 1: "Hannes Leitgeb research"
    *   Sub-query 2: "Hannes Leitgeb upcoming events"

2.  **RAG Retrieval**:
    *   `src/scrapers` content about Hannes Leitgeb's profile and recent publications is retrieved from the **Vector DB**.
    *   *Result*: Text chunks detailing his work on "Logic and Probability".

3.  **Graph Retrieval**:
    *   The **Graph** identifies Hannes Leitgeb as the *Chair of Logic and Philosophy of Language*.
    *   *Result*: Context string: "Hannes Leitgeb LEADS Chair of Logic..."

4.  **MCP Tool Execution**:
    *   The LLM recognizes the second part of the question ("upcoming events") requires precise real-time data.
    *   It calls the tool: `get_events(query="Hannes Leitgeb")`.
    *   The tool scans `data/raw_events.json` and returns: `[{"title": "Talk at LMU", "date": "2024-10-15", ...}]`.


5.  **Final Synthesis**:
    > "Hannes Leitgeb is currently working on Logic and Probability... (from RAG). He leads the Chair of Logic and Philosophy of Language (from Graph). Regarding his schedule, he has an upcoming talk at LMU on October 15th (from MCP Tool)."

## Project Structure

```
mcmp_chatbot/
├── app.py                # Main Streamlit application entry point
├── src/
│   ├── core/             # RAG engine (Gemini), Vector Store (Chroma), Personality loader
│   ├── mcp/              # MCP Tools and Server implementation
│   ├── scrapers/         # Scrapers for MCMP website
│   ├── ui/               # Streamlit UI components
│   └── utils/            # Helper functions (logging, etc.)
├── prompts/              # Chatbot personality configuration
│   └── personality.md    # Leopold's identity, tone, and guidelines
├── data/                 # Local data storage (JSONs, Vector DB)
├── docs/                 # Project documentation and proposals
│   ├── rag_improvements.md
│   ├── HOUSEKEEPING.md   # Maintenance protocols
│   ├── PERSONALITY_AGENT.md # Agent skill for personality design
│   └── MD_CONVENTIONS.md # Markdown conventions
├── scripts/              # Maintenance and update scripts
│   └── update_dataset.py # Main data update script
├── tests/                # Unit and integration tests
├── AGENTS.md             # Guidelines for AI Agents
└── requirements.txt      # Python dependencies
```

## Agentic Workflow

This project uses a structured workflow for AI agents.
- **AGENTS.md**: Read this first if you are an AI assistant.
- **docs/MD_CONVENTIONS.md**: Defines the schema for Markdown files and task management.
