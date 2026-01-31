# Unified Nexus Implementation Plan: RAG + Data Warehouse
- status: active
- type: implementation_plan
- id: unified-nexus-implementation
- last_checked: 2026-01-29
<!-- content -->

## Goal

Unify the existing **Data Warehouse** (DuckDB + CSV/Excel ingestion) with a **RAG architecture** to enable:
1. **Structured queries** → SQL over DuckDB tables  
2. **Unstructured queries** → Semantic search over documents  
3. **Hybrid queries** → Both combined  
4. **MCP protocols** → Agent tools for programmatic access

This plan incorporates proven patterns from [mcmp_chatbot](https://github.com/IgnacioOQ/mcmp_chatbot).

---

## Key Features

### 1. Smart Retrieval (Query Decomposition) ✅

The unified engine automatically breaks down complex multi-part questions into simpler sub-queries for more complete answers.

**How it works:**
- User asks: *"What are our top products and what do customers say about shipping?"*
- Engine decomposes into:
  1. *"What are our top products?"* (structured → SQL)
  2. *"What do customers say about shipping?"* (unstructured → vector search)
- Results from both sub-queries are combined and deduplicated
- LLM generates a unified response

**Implementation:**
```python
@functools.lru_cache(maxsize=128)
def decompose_query(self, user_question) -> tuple[str, ...]
```
- LRU cache prevents repeated LLM calls for identical questions
- Decomposition limited to 1-3 sub-queries to avoid over-fragmentation

### 2. Institutional Graph Layer 🔜

A graph-based layer (`data/graph/`) to understand organizational structure and relationships that are better represented as graphs.

**Use cases:**
- Organizational hierarchy (reporting chains, teams)
- Customer relationships (accounts → contacts → interactions)
- Product dependencies (components → assemblies)
- Document references (policies → procedures → forms)

**Implementation:** `src/core/graph_store.py` (stub ready, full implementation in future phase)

### 3. Performance Optimization: Batch Vector Search ✅

The retrieval engine uses **batch querying** to minimize latency. By sending all decomposed sub-queries to ChromaDB in a single parallel batch request, we achieved an **~82% reduction in retrieval time**.

| Approach | Latency | Notes |
|:---------|:--------|:------|
| Sequential queries | ~0.43s | One query at a time |
| Batch queries | ~0.07s | All queries in parallel |
| **Improvement** | **~82%** | |

**Implementation:**
```python
# Single batch request for all sub-queries
results = self.vector_store.query(
    query_texts=decomposed_queries,  # List of queries
    n_results=top_k
)
```

Combined with deduplication (`seen_ids = set()`), this ensures no duplicate context even when multiple sub-queries return overlapping documents.

---

## Vector Store Selection

**Selected: ChromaDB** (local, lightweight, Python-native)

> [!NOTE]
> **Alternatives considered** (for future reference):
> | Option | Pros | Cons | When to Use |
> |:-------|:-----|:-----|:------------|
> | **LanceDB** | Columnar, fast, embedded | Newer, less community | High-volume analytics |
> | **pgvector** | SQL integration, familiar | Requires PostgreSQL | When consolidating to Postgres |
> | **Pinecone** | Managed, scalable | Cloud-only, costs | Enterprise scale |
> | **Weaviate** | GraphQL, rich features | Heavier setup | Complex schema needs |

---

## Data Types & Handling Strategy

| Data Type | Current | New Handler | Storage | Notes |
|:----------|:--------|:------------|:--------|:------|
| **CSV/Excel** | ✅ `ingestion.py` | Keep | DuckDB | Tabular queries |
| **JSON (tabular)** | ✅ `ingestion.py` | Keep | DuckDB | Tabular queries |
| **Plain Text (.txt)** | ❌ | `DocumentIngester` | ChromaDB | Semantic search |
| **Markdown (.md)** | ❌ | `DocumentIngester` | ChromaDB | Header-aware chunking |
| **PDF** | ❌ | `DocumentIngester` | ChromaDB | Requires `pypdf` |
| **DOCX** | ❌ | `DocumentIngester` | ChromaDB | Requires `python-docx` |
| **JSON (nested)** | ❌ | MCP Tools | Both | Hybrid access |

---

## Proposed Changes

### New Core Components

---

#### [NEW] `src/core/vector_store.py`

ChromaDB wrapper implementing mcmp_chatbot patterns:

- **Batch queries**: Accept list of query texts for parallel retrieval
- **Upsert support**: Update existing docs, insert new ones
- **Metadata filtering**: `where` parameter for structured filters
- **Deduplication**: Content-hash based IDs
- **Embedding**: `all-MiniLM-L6-v2` (local, free)

```python
# Key method signature
def query(self, query_texts, n_results=3, where=None) -> dict
```

---

#### [NEW] `src/core/query_router.py`

Classifies queries into `STRUCTURED` / `UNSTRUCTURED` / `HYBRID`:

- Keyword heuristics (fast, no LLM cost)
- LLM fallback for ambiguous cases
- `QueryType` enum for type safety

---

#### [NEW] `src/core/text2sql.py`

Natural language → SQL for DuckDB:

- Schema introspection with sample data
- SQL generation via LLM
- Query validation before execution

---

#### [NEW] `src/core/unified_engine.py`

Main orchestrator (inspired by mcmp_chatbot `RAGEngine`):

- **Query decomposition** with LRU caching (Smart Retrieval)
- **Batch vector search** for 82% latency reduction
- **Multi-source retrieval**: VectorStore + DuckDB + Graph
- **Context assembly**: Format results for LLM
- **MCP integration** (optional, toggleable)

```python
# Key method signatures
@functools.lru_cache(maxsize=128)
def decompose_query(self, user_question) -> list[str]

def retrieve_with_decomposition(self, question, top_k=3) -> list[dict]

def generate_response(self, query, use_mcp_tools=False) -> str
```

---

#### [NEW] `src/core/document_ingestion.py`

Document processing pipeline:

- **Chunking strategies**: size-based, header-based (for MD)
- **File readers**: TXT, MD, PDF, DOCX
- **Metadata extraction**: source, type, timestamps

---

#### [NEW] `src/core/graph_store.py` ✅

Institutional graph for organizational relationships:

- **Node types**: person, team, department, document, product, customer
- **Relationship types**: reports_to, manages, belongs_to, owns, references
- **Traversal queries**: path finding, subgraph extraction
- **Context extraction**: augments retrieval with organizational knowledge
- **Persistence**: JSON files in `data/graph/`

```python
# Key method signatures
def add_node(self, node: GraphNode) -> bool
def add_edge(self, edge: GraphEdge) -> bool
def traverse(self, start_id, relationship, direction, max_depth) -> GraphQueryResult
def get_context_for_query(self, entity_names: list[str]) -> str
```

---

#### [NEW] `src/mcp/` (Phase 5)

MCP Server for structured data tools:

- `search_tables`: Query DuckDB metadata
- `get_schema`: Retrieve table schemas
- `execute_query`: Run validated SQL

---

### Modified Files

---

#### [MODIFY] `requirements.txt`

```diff
+ chromadb>=0.4.0
+ sentence-transformers>=2.0.0
+ rank-bm25>=0.2.0
+ pypdf>=3.0.0
+ python-docx>=0.8.0
```

---

#### [MODIFY] `src/app.py`

- Add document uploader in sidebar
- Display query type badges in chat
- Show system stats (tables, documents)
- MCP toggle (optional)

---

## Implementation Phases

### Phase 1: Vector Store Foundation (2h) ✅
- [x] Create `src/core/vector_store.py`
- [x] Create `src/core/document_ingestion.py`  
- [x] Update `requirements.txt`
- [x] Test: ingest sample docs, run queries

### Phase 2: Query Routing (1h) ✅
- [x] Create `src/core/query_router.py`
- [x] Test: classify diverse query types

### Phase 3: Text2SQL (2h) ✅
- [x] Create `src/core/text2sql.py`
- [x] Test: generate SQL from natural language

### Phase 4: Unified Engine (3h) ✅
- [x] Create `src/core/unified_engine.py`
- [x] Implement query decomposition with caching
- [x] Integrate all retrieval paths
- [x] Test: end-to-end queries

### Phase 5: UI + MCP (2h) ✅
- [x] Modify `src/app.py` for document upload
- [x] Create `src/mcp/` directory and server (12 tools)
- [x] Update `src/components/sidebar.py` with Tables/Documents/Graph tabs
- [x] Update `src/components/chat.py` with Unified Engine integration
- [x] Test: full workflow in Streamlit

---

## Verification Plan

### Automated Tests

```bash
# After each phase
pytest tests/ -v
```

| Test File | Coverage |
|:----------|:---------|
| `test_vector_store.py` | Add/query/dedupe operations |
| `test_query_router.py` | Classification accuracy |
| `test_document_ingestion.py` | Chunking, file reading |
| `test_unified_engine.py` | End-to-end retrieval |

### Manual Verification

1. **Streamlit smoke test**: `streamlit run src/app.py`
2. **Structured query**: "How many rows in sales_data?"
3. **Unstructured query**: "What does the policy say about X?"
4. **Hybrid query**: "Which customers mentioned pricing and spent >$1K?"

---

## Key Patterns from mcmp_chatbot

| Pattern | Benefit | Implementation |
|:--------|:--------|:---------------|
| **Batch queries** | 82% latency reduction | `vs.query(query_texts=[...])` |
| **Query decomposition** | Better recall for complex Q | `@lru_cache` decorated method |
| **Deduplication** | No duplicate context | `seen_ids = set()` |
| **Metadata filtering** | Precise structured access | `where={"type": "event"}` |
| **MCP toggle** | Control latency/cost | Sidebar checkbox |
