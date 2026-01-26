# MCMP Chatbot

- status: active
- context_dependencies: {"agents": "AGENTS.md", "conventions": "MD_CONVENTIONS.md"}

<!-- content -->

A RAG-based (Retrieval-Augmented Generation) chatbot for the **Munich Center for Mathematical Philosophy (MCMP)**. This application scrapes the MCMP website for the latest events, people, and research, and uses an LLM (Google Gemini, OpenAI, or Anthropic) to answer user queries about the center's activities.

The application is built with **Streamlit** for the frontend, uses **ChromaDB** for vector storage, and integrates with **Google Sheets** for cloud-based feedback collection.

## Features

- **Activity QA**: Ask about upcoming talks, reading groups, and events.
- **Automated Scraping**: Keeps data fresh by scraping the MCMP website.
- **RAG Architecture**: Uses vector embeddings to retrieve relevant context for accurate answers.
- **Cloud Database (Feedback)**: User feedback is automatically saved to a Google Sheet for persistent, cloud-based storage (with a local JSON fallback).
- **Multi-LLM Support**: Configured to work seamlessly with **Google Gemini**, but also supports OpenAI and Anthropic.
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
   Create a `.streamlit/secrets.toml` file with your API keys.

   **For Google Gemini (Recommended):**
   - Get your API key from [Google AI Studio](https://aistudio.google.com/).
   ```toml
   GEMINI_API_KEY = "your-google-gemini-key"
   ```

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

## Technical Architecture

### 1. Frontend: Streamlit
The user interface is built entirely in **Streamlit**, providing a clean, responsive chat interface. It handles user sessions, admin access (password protected), and feedback forms directly in the browser.

### 2. AI Engine: Google Gemini
The core logic (`src/core/engine.py`) connects to the **Gemini API** (or others) to generate responses. It prompts the model with retrieved context from the vector store to ensure accuracy and minimize hallucinations.

### 3. Data Storage
- **Vector Database**: Scraped content is chunked and embedded into a local **ChromaDB** instance (`data/vectordb`) for fast semantic retrieval.
- **Cloud Feedback**: User feedback is pushed to **Google Sheets** via the Google Drive API, acting as a cloud database for ongoing user data collection.

## Project Structure

```
mcmp_chatbot/
├── app.py                # Main Streamlit application entry point
├── src/
│   ├── core/             # RAG engine (Gemini) and Vector Store (Chroma)
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
