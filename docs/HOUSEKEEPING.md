# Housekeeping Protocol
- status: recurring
- type: guideline
- label: [agent]
<!-- content -->
1. Read the AGENTS.md file.
2. Look at the dependency network of the project, namely which script refers to which one.
3. Proceed doing different sanity checks and unit tests from root scripts to leaves.
4. Compile all errors and tests results into a report. Make sure that the report uses the proper syntax protocol as defined in MD_CONVENTIONS.md. If necessary, you can always use the scripts in the language folder to help you with this.
6. Print that report in the Latest Report subsection below, overwriting previous reports.
7. Add that report to the content/logs/AGENTS_LOG.md.

<!-- MERGED FROM NEWER VERSION -->

- context_dependencies: {"conventions": "MD_CONVENTIONS.md", "agents": "../AGENTS.md"}
<!-- content -->
1. Read the AGENTS.md file and the MD_CONVENTIONS.md file.
2. Look at the dependency network of the project, namely which script refers to which one.
3. Update the dataset by running the scraper scripts and making sure things are in order.
4. Proceed doing different sanity checks and unit tests from root scripts to leaves.
5. Compile all errors and tests results into a report. Make sure that the report uses the proper syntax protocol as defined in MD_CONVENTIONS.md. If necessary, you can always use the scripts in the language folder to help you with this.
6. Print that report in the Latest Report subsection below, overwriting previous reports.
7. Add that report to the content/logs/AGENTS_LOG.md.
8. Commit and push the changes.

## Current Project Housekeeping
- status: active
- type: plan
- label: [agent, recurring]
<!-- content -->

## Dependency Network
- status: active
- type: task
- label: [agent]
<!-- content -->
Based on post-React integration analysis:
- **Core Modules:**
- **Advanced Modules:**
- **Engine Module:**
- **API Module:**
- **Tests:**
- **Notebooks:**

<!-- MERGED FROM NEWER VERSION -->

Based on codebase analysis (2026-01-28):

### 1. Application Layer (Entry Point)
- id: housekeeping_protocol.dependency_network.1_application_layer_entry_point
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
- **`app.py`**: Main Streamlit application.
  - *Dependencies*: `src.core.engine`, `src.core.vector_store` (dynamic), `src.scrapers.mcmp_scraper` (dynamic), `gspread` (optional).
  - *Role*: Handles UI, user state, and orchestration of scraping/indexing.

### 2. Core Engine Layer
- id: housekeeping_protocol.dependency_network.2_core_engine_layer
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
- **`src/core/engine.py`**: RAGEngine class.
  - *Dependencies*: `src.core.vector_store`, `src.utils.logger`, `openai`, `anthropic`, `google.genai`.
  - *Role*: Query decomposition, LLM interaction, response generation.
- **`src/core/vector_store.py`**: VectorStore class.
  - *Dependencies*: `chromadb`, `src.utils.logger`.
  - *Role*: Manages ChromaDB, embedding functions, and document indexing.

### 3. Data Acquisition Layer (Scrapers)
- id: housekeeping_protocol.dependency_network.3_data_acquisition_layer_scrapers
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
- **`src/scrapers/mcmp_scraper.py`**: MCMPScraper class.
  - *Dependencies*: `requests`, `bs4`, `src.utils.logger`.
  - *Role*: Scrapes events, people, and research from MCMP website; runs standard cleaning.

### 4. Utilities & Scripts
- id: housekeeping_protocol.dependency_network.4_utilities_scripts
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
- **`src/utils/logger.py`**: centralized logging.
- **`scripts/update_knowledge.py`**: specific script for parsing markdown knowledge.
- **`scripts/test_sheets_connection.py`**: connection test for Google Sheets.

## Latest Report
- status: active
- type: task
- owner: Antigravity
- label: [agent]
<!-- content -->
**Execution Date:** 2026-01-19

**Test Results:**
1. `tests/test_api.py`: **Passed** (17 tests).
2. `tests/test_engine.py`: **Passed** (16 tests).
3. `tests/test_mechanics.py`: **Passed** (4 tests).
4. `tests/test_proxy_simulation.py`: **Passed** (1 test).

**Total: 38 tests passed.**

**Summary:**
All unit tests passed. `verify_logging.py` confirmed correct simulation flow and logging. Data persistence features have been integrated and verified locally. Project is stable.

<!-- MERGED FROM NEWER VERSION -->

**Execution Date:** 2026-01-28 (Antigravity)

**Status Checks:**
1.  **Data Update (`src/scrapers/mcmp_scraper.py`)**: **Passed**.
    - Scraper successfully updated. Output summary: "Scraped 3 events, 82 people, 2 research items, 7 general items."
2.  **Vector Store (`src/core/vector_store.py`)**: **Failed**.
    - Unit tests failed due to missing `chromadb` dependency.
3.  **Connectivity (`scripts/test_sheets_connection.py`)**: **Skipped**.
    - Secrets likely missing in environment.
4.  **Unit Tests**: **Mixed**.
    - `tests/test_scraper.py`: **Passed**.
    - `tests/test_engine.py`: **Failed** (`ModuleNotFoundError: No module named 'chromadb'`).
    - `tests/test_vector_store.py`: **Failed** (`ModuleNotFoundError: No module named 'chromadb'`).
    - `tests/test_graph_manual.py`: **Failed** (`AssertionError: No nodes loaded`).

**Summary:**
System health check failed. Critical dependency `chromadb` is missing from the environment, causing core engine and vector store tests to fail. Graph retrieval also failed to load nodes. Scrapers are operational.

**Action Items:**
- [ ] Install `chromadb`.
- [ ] Debug `GraphUtils` node loading.
- [ ] Provide `.streamlit/secrets.toml`.

<!-- MERGED FROM NEWER VERSION -->

**Execution Date:** 2026-01-31 (Antigravity)

**Status Checks:**
1.  **Data Update (`src/scrapers/mcmp_scraper.py`)**: **Passed**.
    - **Selenium Enabled**: Yes.
    - Stats: **53 events** (Exhaustive scrape success), 82 people, 4 research items, 7 general items.
2.  **Vector Store (`src/core/vector_store.py`)**: **Passed**.
    - Unit tests (`tests/test_vector_store.py`) passed.
3.  **Connectivity (`scripts/test_sheets_connection.py`)**: **Passed**.
    - Google Sheets authentication and write test successful.
4.  **Unit Tests**: **Mixed**.
    - `tests/test_engine.py`: **Passed**.
    - `tests/test_vector_store.py`: **Passed**.
    - `tests/test_scraper.py`: **Passed**.
    - `tests/test_graph_correctness.py`: **Passed**.
    - `tests/test_mcp.py`: **Failed**.
        - `test_search_people` failed: `search_people("Bonatti", role_filter="Doctoral fellow")` returned 0 results.

**Summary:**
Housekeeping successfully restored the exhaustive event scraper by installing missing Selenium dependencies. Database is now fully populated with 53 upcoming events. One minor regression remains in MCP role filtering.

**Action Items:**
- [ ] Debug `search_people` in `src/mcp/tools.py` or check if "Bonatti" role data changed.
