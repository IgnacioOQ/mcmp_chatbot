# MCMP Chatbot

- status: active
- context_dependencies: {"agents": "AGENTS.md", "conventions": "MD_CONVENTIONS.md"}

<!-- content -->

A RAG-based (Retrieval-Augmented Generation) chatbot for the **Munich Center for Mathematical Philosophy (MCMP)**. This application scrapes the MCMP website for the latest events, people, and research, and uses an LLM to answer user queries about the center's activities.

## Features

- **Activity QA**: Ask about upcoming talks, reading groups, and events.
- **Automated Scraping**: Keeps data fresh by scraping the MCMP website.
- **RAG Architecture**: Uses vector embeddings to retrieve relevant context for accurate answers.
- **Feedback Loop**: Collects user feedback via Google Sheets or local storage.
- **Agentic Workflow**: Follows the `AGENTS.md` and `MD_CONVENTIONS.md` protocols for AI-assisted development.

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
   - Create a `.streamlit/secrets.toml` file (see `.env.example` or project documentation for keys).
   - Required keys: `gcp_service_account` (for Sheets), API keys for the LLM provider (Gemini/OpenAI/etc.).

4. **Run the Application**:
   ```bash
   streamlit run app.py
   ```

## Project Structure

```
mcmp_chatbot/
├── app.py                # Main Streamlit application entry point
├── src/
│   ├── core/             # RAG engine and Vector Store logic
│   ├── scrapers/         # Scrapers for MCMP website
│   └── utils/            # Helper functions (logging, etc.)
├── data/                 # Local data storage (JSONs, Vector DB)
├── AGENTS.md             # Guidelines for AI Agents
├── MD_CONVENTIONS.md     # Markdown conventions for the project
└── requirements.txt      # Python dependencies
```

## Agentic Workflow

This project uses a structured workflow for AI agents.
- **AGENTS.md**: Read this first if you are an AI assistant.
- **MD_CONVENTIONS.md**: Defines the schema for Markdown files and task management.
- **IMPLEMENTATION_PLAN.md**: Tracks current development goals.
