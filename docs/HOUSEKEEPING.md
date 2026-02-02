# Housekeeping Protocol
- status: recurring
- type: guideline
- context_dependencies: {"conventions": "MD_CONVENTIONS.md", "agents": "../AGENTS.md"}
<!-- content -->
1. Read the AGENTS.md file and the MD_CONVENTIONS.md file.
2. Look at the dependency network of the project, namely which script refers to which one.
3. Update the dataset by running the scraper scripts and making sure things are in order.
4. Proceed doing different sanity checks and unit tests from root scripts to leaves.
5. Compile all errors and tests results into a report. Make sure that the report uses the proper syntax protocol as defined in MD_CONVENTIONS.md. If necessary, you can always use the scripts in the language folder to help you with this.
6. Print that report in the Latest Report subsection below, overwriting previous reports.
7. Add that report to the AGENTS_LOG.md.
8. Commit and push the changes.

## Current Project Housekeeping
- status: active
- type: recurring
<!-- content -->

## Dependency Network
- status: active
- type: task
<!-- content -->
Based on codebase analysis (2026-01-28):

### 1. Application Layer (Entry Point)
- **`app.py`**: Main Streamlit application.
  - *Dependencies*: `src.core.engine`, `src.core.vector_store` (dynamic), `src.scrapers.mcmp_scraper` (dynamic), `gspread` (optional).
  - *Role*: Handles UI, user state, and orchestration of scraping/indexing.

### 2. Core Engine Layer
- **`src/core/engine.py`**: RAGEngine class.
  - *Dependencies*: `src.core.vector_store`, `src.utils.logger`, `openai`, `anthropic`, `google.genai`.
  - *Role*: Query decomposition, LLM interaction, response generation.
- **`src/core/vector_store.py`**: VectorStore class.
  - *Dependencies*: `chromadb`, `src.utils.logger`.
  - *Role*: Manages ChromaDB, embedding functions, and document indexing.

### 3. Data Acquisition Layer (Scrapers)
- **`src/scrapers/mcmp_scraper.py`**: MCMPScraper class.
  - *Dependencies*: `requests`, `bs4`, `src.utils.logger`.
  - *Role*: Scrapes events, people, and research from MCMP website; runs standard cleaning.

### 4. Utilities & Scripts
- **`src/utils/logger.py`**: centralized logging.
- **`scripts/update_knowledge.py`**: specific script for parsing markdown knowledge.
- **`scripts/test_sheets_connection.py`**: connection test for Google Sheets.

## Latest Report
- status: active
- type: task
- owner: Jules
<!-- content -->
**Execution Date:** 2026-02-02 (Jules)

**Status Checks:**
1.  **Data Update (`src/scrapers/mcmp_scraper.py`)**: **Passed**.
    - **Selenium Enabled**: Yes.
    - Stats: **53 events**, 82 people, 4 research items, 7 general items.
2.  **Vector Store (`src/core/vector_store.py`)**: **Passed**.
    - Unit tests (`tests/test_vector_store.py`) passed.
3.  **Connectivity (`scripts/test_sheets_connection.py`)**: **Skipped**.
    - Reason: Missing `.streamlit/secrets.toml` in environment.
4.  **Unit Tests**: **Passed**.
    - `tests/test_engine.py`: **Passed**.
    - `tests/test_vector_store.py`: **Passed**.
    - `tests/test_scraper.py`: **Passed**.
    - `tests/test_graph_correctness.py`: **Passed**.
    - `tests/test_mcp.py`: **Passed**. (Fixed regression in `test_search_people`).

**Summary:**
Executed housekeeping protocol. Restored data by creating missing `data/graph` directory and running update script. Fixed regression in `src/mcp/tools.py` where `search_people` role filter was failing due to metadata key mismatch ("role" vs "position"). All tests passed.

**Action Items:**
- [ ] Restore `.streamlit/secrets.toml` if deploying to production.
