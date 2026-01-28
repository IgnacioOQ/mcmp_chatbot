# RAG Optimization Agent Skill
- status: active
- type: agent_skill
- id: rags-agent
- context_dependencies: {"conventions": "MD_CONVENTIONS.md"}
- last_checked: 2025-01-27
<!-- content -->
This document defines an **agent skill** for analyzing, configuring, and improving Retrieval-Augmented Generation (RAG) systems across different projects. The agent equipped with this skill can diagnose RAG performance issues and implement cost-effective improvements.

## Core Competencies
- status: active
- type: guideline
- id: rags-agent.competencies
<!-- content -->
An agent with this skill can:

1. **Audit** existing RAG implementations for common failure modes
2. **Recommend** retrieval strategies matched to data characteristics
3. **Implement** chain-of-thought and multi-step retrieval patterns
4. **Design** MCP-based structured data access layers
5. **Optimize** the cost/quality tradeoff for production systems

## RAG Fundamentals
- status: active
- type: guideline
- id: rags-agent.fundamentals
<!-- content -->
Before optimizing, ensure the foundational RAG architecture is sound. This section covers the essential components and common pitfalls.

### What RAG Actually Does
- status: active
- type: context
- id: rags-agent.fundamentals.definition
<!-- content -->
RAG combines three operations:

1. **Retrieval**: Given a query, find relevant documents from a corpus using semantic similarity (embeddings) or keyword matching (BM25)
2. **Augmentation**: Inject the retrieved documents into the LLM's context window as grounding information
3. **Generation**: The LLM produces a response conditioned on both the query and the retrieved context

The quality of a RAG system is bounded by retrieval quality. If relevant documents are not retrieved, the LLM cannot use them regardless of its capability.

### Essential Components
- status: active
- type: guideline
- id: rags-agent.fundamentals.components
<!-- content -->
A well-structured RAG system requires:

| Component | Purpose | Common Choices |
|:----------|:--------|:---------------|
| Document Store | Raw text storage | JSON files, PostgreSQL, S3 |
| Vector Database | Embedding storage and similarity search | ChromaDB, Pinecone, Weaviate, pgvector |
| Embedding Model | Convert text to vectors | `all-MiniLM-L6-v2`, OpenAI `text-embedding-3-small`, Cohere |
| Chunking Strategy | Split documents into retrievable units | Fixed-size, semantic, recursive |
| Retrieval Logic | Query the vector DB and rank results | Top-k, MMR, hybrid |
| LLM | Generate responses from context | GPT-4, Claude, Gemini, Llama |

### Chunking Strategy Guidelines
- status: active
- type: guideline
- id: rags-agent.fundamentals.chunking
<!-- content -->
Chunk size directly impacts retrieval quality:

- **Too small** (< 100 tokens): Loses context, retrieves fragments
- **Too large** (> 1000 tokens): Dilutes relevance signal, wastes context window
- **Sweet spot**: 200-500 tokens with 10-20% overlap

Recommended approaches by content type:

| Content Type | Strategy | Chunk Size | Overlap |
|:-------------|:---------|:-----------|:--------|
| Documentation | Recursive by headers | 300-500 tokens | 50 tokens |
| Code | By function/class | Natural boundaries | None |
| Conversations | By turn or topic | 200-400 tokens | 1-2 turns |
| Academic papers | By section | 400-600 tokens | 100 tokens |

### Embedding Model Selection
- status: active
- type: guideline
- id: rags-agent.fundamentals.embeddings
<!-- content -->
Choose embedding models based on your constraints:

| Model | Dimensions | Speed | Quality | Cost |
|:------|:-----------|:------|:--------|:-----|
| `all-MiniLM-L6-v2` | 384 | Fast | Good | Free |
| `all-mpnet-base-v2` | 768 | Medium | Better | Free |
| `text-embedding-3-small` | 1536 | Fast | Very Good | $0.02/1M tokens |
| `text-embedding-3-large` | 3072 | Medium | Excellent | $0.13/1M tokens |

For most projects, `all-MiniLM-L6-v2` or `text-embedding-3-small` provides the best cost/quality ratio.

### Common Failure Modes
- status: active
- type: guideline
- id: rags-agent.fundamentals.failures
<!-- content -->
Diagnose RAG issues by checking these failure modes in order:

1. **Retrieval Miss**: Relevant documents exist but are not retrieved
   - *Symptom*: LLM says "I don't have information about X" when X is in the corpus
   - *Cause*: Query/document embedding mismatch, poor chunking, insufficient top-k

2. **Context Dilution**: Too many irrelevant chunks crowd out relevant ones
   - *Symptom*: Vague or generic answers despite good data
   - *Cause*: top-k too high, no reranking, poor chunk boundaries

3. **Lost in the Middle**: Relevant info retrieved but ignored by LLM
   - *Symptom*: Correct chunks in context but answer ignores them
   - *Cause*: Critical info buried in middle of long context
   - *Fix*: Place most relevant chunks first and last

4. **Hallucination Despite Context**: LLM invents information
   - *Symptom*: Confident wrong answers
   - *Cause*: Weak grounding prompt, context not authoritative enough

## Retrieval Improvements
- status: active
- type: plan
- id: rags-agent.retrieval
<!-- content -->
This section covers techniques to improve what documents are retrieved for a given query.

### Query Decomposition
- status: active
- type: task
- id: rags-agent.retrieval.decomposition
- priority: high
- estimate: 15m
<!-- content -->
Break complex questions into simpler sub-queries before retrieval. This is the highest-impact, lowest-cost improvement.

**When to use**: Questions with multiple parts, comparisons, or implicit sub-questions.

**Implementation**:

```python
def decompose_query(question: str, llm_client) -> list[str]:
    """
    Decompose a complex question into simpler search queries.
    
    Args:
        question: The original user question
        llm_client: LLM client for decomposition
    
    Returns:
        List of 1-4 sub-queries including the original
    """
    # Minimal prompt to keep costs low
    prompt = f"""Break this question into 1-3 simple search queries:
"{question}"

Return ONLY the queries, one per line. If already simple, return as-is."""
    
    response = llm_client.generate_content(prompt)
    queries = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
    
    # Always include original, cap at 4 total
    if question not in queries:
        queries.insert(0, question)
    return queries[:4]


def retrieve_with_decomposition(question: str, vector_store, llm_client, top_k: int = 3) -> list[dict]:
    """
    Retrieve using decomposed queries, deduplicate results.
    
    Args:
        question: Original question
        vector_store: Vector database instance
        llm_client: LLM for decomposition
        top_k: Results per sub-query
    
    Returns:
        Deduplicated list of chunks with source query tracking
    """
    queries = decompose_query(question, llm_client)
    
    all_chunks = []
    seen_ids = set()
    
    for query in queries:
        results = vector_store.query(query_texts=[query], n_results=top_k)
        
        for i, doc_id in enumerate(results['ids'][0]):
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_chunks.append({
                    'id': doc_id,
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'source_query': query
                })
    
    return all_chunks
```

**Cost impact**: +1 small LLM call (~5-10% increase)

### Step-Back Prompting
- status: active
- type: task
- id: rags-agent.retrieval.stepback
- priority: high
- estimate: 15m
<!-- content -->
Generate a more abstract version of the question to retrieve broader context that keyword-specific queries miss.

**When to use**: Specific questions that require general background, questions with jargon or abbreviations.

**Implementation**:

```python
def step_back_retrieval(question: str, vector_store, llm_client, top_k: int = 3) -> list[dict]:
    """
    Retrieve using both the original and a step-back (abstracted) question.
    
    The step-back question captures broader context that helps answer
    specific queries (e.g., "When is Dr. Smith's talk?" -> "What talks are scheduled?")
    
    Args:
        question: Original specific question
        vector_store: Vector database instance
        llm_client: LLM client
        top_k: Results per query
    
    Returns:
        Combined, deduplicated chunks from both queries
    """
    # Generate step-back question
    step_back_prompt = f"""Given this specific question:
"{question}"

What is a more general question that would provide helpful context?
Example: "When is Dr. Smith's talk?" -> "What talks are scheduled?"

Respond with ONLY the general question."""
    
    response = llm_client.generate_content(step_back_prompt)
    abstract_question = response.text.strip()
    
    # Retrieve for both
    all_chunks = []
    seen_hashes = set()
    
    for query in [question, abstract_question]:
        results = vector_store.query(query_texts=[query], n_results=top_k)
        
        for i, doc in enumerate(results['documents'][0]):
            doc_hash = hash(doc[:100])
            if doc_hash not in seen_hashes:
                seen_hashes.add(doc_hash)
                all_chunks.append({
                    'text': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'query_type': 'original' if query == question else 'step_back'
                })
    
    return all_chunks
```

**Cost impact**: +1 small LLM call (~5-10% increase)

### Hybrid Search
- status: active
- type: task
- id: rags-agent.retrieval.hybrid
- priority: medium
- estimate: 30m
<!-- content -->
Combine semantic (embedding) search with keyword (BM25) search. This catches both conceptually similar and lexically similar documents.

**When to use**: Technical documentation with specific terminology, proper nouns, code identifiers.

**Implementation**:

```python
from rank_bm25 import BM25Okapi
from typing import Optional

class HybridRetriever:
    """
    Combines vector similarity search with BM25 keyword search.
    
    The final ranking uses Reciprocal Rank Fusion (RRF) to merge
    the two result lists without requiring score normalization.
    """
    
    def __init__(self, vector_store, documents: list[dict]):
        """
        Initialize hybrid retriever.
        
        Args:
            vector_store: ChromaDB or similar vector store
            documents: List of dicts with 'id' and 'text' keys
        """
        self.vector_store = vector_store
        self.documents = {doc['id']: doc for doc in documents}
        
        # Build BM25 index
        tokenized = [doc['text'].lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized)
        self.doc_ids = [doc['id'] for doc in documents]
    
    def search(self, query: str, top_k: int = 5, alpha: float = 0.5) -> list[dict]:
        """
        Perform hybrid search combining vector and keyword retrieval.
        
        Args:
            query: Search query
            top_k: Number of results to return
            alpha: Weight for vector search (1-alpha for BM25)
        
        Returns:
            Ranked list of documents
        """
        # Vector search
        vector_results = self.vector_store.query(
            query_texts=[query], 
            n_results=top_k * 2
        )
        vector_ranks = {
            doc_id: rank 
            for rank, doc_id in enumerate(vector_results['ids'][0])
        }
        
        # BM25 search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_ranked = sorted(
            enumerate(bm25_scores), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_k * 2]
        bm25_ranks = {
            self.doc_ids[idx]: rank 
            for rank, (idx, _) in enumerate(bm25_ranked)
        }
        
        # Reciprocal Rank Fusion
        k = 60  # RRF constant
        all_doc_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        
        rrf_scores = {}
        for doc_id in all_doc_ids:
            vector_rrf = alpha / (k + vector_ranks.get(doc_id, 1000))
            bm25_rrf = (1 - alpha) / (k + bm25_ranks.get(doc_id, 1000))
            rrf_scores[doc_id] = vector_rrf + bm25_rrf
        
        # Sort by RRF score and return top_k
        ranked_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        return [self.documents[doc_id] for doc_id in ranked_ids[:top_k]]
```

**Cost impact**: No LLM calls, minor compute overhead

### Reranking
- status: active
- type: task
- id: rags-agent.retrieval.reranking
- priority: medium
- estimate: 20m
<!-- content -->
After initial retrieval, use a cross-encoder model to rerank results. Cross-encoders are more accurate than bi-encoders (embeddings) but slower, so use them only on the top candidates.

**When to use**: When retrieval recall is good but precision is poor (lots of semi-relevant results).

**Implementation**:

```python
from sentence_transformers import CrossEncoder

class Reranker:
    """
    Reranks retrieved documents using a cross-encoder model.
    
    Cross-encoders score query-document pairs directly, providing
    more accurate relevance estimates than embedding similarity.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize reranker with a cross-encoder model.
        
        Args:
            model_name: HuggingFace model identifier
        """
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
        """
        Rerank documents by relevance to the query.
        
        Args:
            query: Search query
            documents: List of dicts with 'text' key
            top_k: Number of documents to return
        
        Returns:
            Reranked list of documents with added 'rerank_score'
        """
        if not documents:
            return []
        
        # Create query-document pairs
        pairs = [(query, doc['text']) for doc in documents]
        
        # Score all pairs
        scores = self.model.predict(pairs)
        
        # Add scores and sort
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        ranked = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        return ranked[:top_k]
```

**Cost impact**: ~50-100ms per rerank call, no API costs (local model)

## Chain-of-Thought Patterns
- status: active
- type: plan
- id: rags-agent.cot
<!-- content -->
These patterns make the LLM "think" more carefully about what information it needs, leading to better retrieval and answers.

### Self-Ask Pattern
- status: active
- type: task
- id: rags-agent.cot.selfask
- priority: medium
- estimate: 30m
<!-- content -->
The LLM generates follow-up questions and retrieves answers iteratively until it has enough information.

**When to use**: Complex questions requiring multiple facts, multi-hop reasoning.

**Implementation**:

```python
def self_ask_rag(question: str, vector_store, llm_client, max_iterations: int = 2) -> str:
    """
    Implement Self-Ask pattern: LLM asks itself follow-up questions
    and retrieves information to answer them iteratively.
    
    Args:
        question: Original user question
        vector_store: Vector database instance
        llm_client: LLM client
        max_iterations: Maximum follow-up rounds (keep low for cost)
    
    Returns:
        Final answer string
    """
    accumulated_context = []
    
    # Initial retrieval
    initial_results = vector_store.query(query_texts=[question], n_results=5)
    accumulated_context.extend(initial_results['documents'][0])
    
    current_question = question
    
    for iteration in range(max_iterations):
        # Ask LLM if it needs more information
        check_prompt = f"""Question: "{current_question}"

Context found so far:
{chr(10).join(accumulated_context[-5:])}

Do you need to search for more information to answer fully?
If YES: respond with SEARCH: [your search query]
If NO: respond with READY"""
        
        check_response = llm_client.generate_content(check_prompt)
        response_text = check_response.text.strip()
        
        if response_text.startswith("SEARCH:"):
            # Extract follow-up query and retrieve
            follow_up = response_text.replace("SEARCH:", "").strip()
            follow_up_results = vector_store.query(
                query_texts=[follow_up], 
                n_results=3
            )
            
            # Add new unique context
            for doc in follow_up_results['documents'][0]:
                if doc not in accumulated_context:
                    accumulated_context.append(doc)
        else:
            break
    
    # Generate final answer
    final_prompt = f"""Answer this question: "{question}"

Use ONLY this information:
{chr(10).join(accumulated_context)}

If the information is insufficient, say so clearly."""
    
    return llm_client.generate_content(final_prompt).text
```

**Cost impact**: +2-4 LLM calls per question (~30-50% increase)

### Verify-Then-Answer
- status: active
- type: task
- id: rags-agent.cot.verify
- priority: low
- estimate: 20m
<!-- content -->
After generating an answer, have the LLM verify each claim against the retrieved context.

**When to use**: High-stakes applications where accuracy is critical.

**Implementation**:

```python
def verify_then_answer(question: str, context: list[str], llm_client) -> dict:
    """
    Generate an answer, then verify each claim against context.
    
    Args:
        question: User question
        context: Retrieved context chunks
        llm_client: LLM client
    
    Returns:
        Dict with 'answer', 'claims', and 'verification_status'
    """
    context_text = chr(10).join(context)
    
    # Step 1: Generate answer with explicit claims
    answer_prompt = f"""Answer this question based on the context:
Question: {question}

Context:
{context_text}

Format your answer as:
ANSWER: [your answer]
CLAIMS:
1. [first factual claim]
2. [second factual claim]
..."""
    
    answer_response = llm_client.generate_content(answer_prompt)
    
    # Parse answer and claims
    lines = answer_response.text.strip().split('\n')
    answer = ""
    claims = []
    in_claims = False
    
    for line in lines:
        if line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "").strip()
        elif line.startswith("CLAIMS:"):
            in_claims = True
        elif in_claims and line.strip():
            # Remove numbering
            claim = line.strip().lstrip("0123456789.)-").strip()
            if claim:
                claims.append(claim)
    
    # Step 2: Verify each claim
    verification_results = []
    for claim in claims:
        verify_prompt = f"""Is this claim supported by the context?

Claim: {claim}

Context:
{context_text}

Respond with ONLY: SUPPORTED, UNSUPPORTED, or PARTIALLY_SUPPORTED"""
        
        verify_response = llm_client.generate_content(verify_prompt)
        status = verify_response.text.strip().upper()
        verification_results.append({
            'claim': claim,
            'status': status if status in ['SUPPORTED', 'UNSUPPORTED', 'PARTIALLY_SUPPORTED'] else 'UNKNOWN'
        })
    
    return {
        'answer': answer,
        'claims': verification_results,
        'all_supported': all(v['status'] == 'SUPPORTED' for v in verification_results)
    }
```

**Cost impact**: +N LLM calls where N = number of claims (~50-100% increase)

## MCP-Based Data Access
- status: active
- type: plan
- id: rags-agent.mcp
<!-- content -->
Instead of dumping text chunks to the LLM, expose structured tools via MCP (Model Context Protocol). This lets the LLM query data more precisely.

### Why MCP for RAG
- status: active
- type: context
- id: rags-agent.mcp.rationale
<!-- content -->
Traditional RAG returns text chunks. MCP exposes **semantic operations**:

| Traditional RAG | MCP Approach |
|:----------------|:-------------|
| Returns: "Event: AI Workshop, Date: Jan 15..." | `get_events(type="workshop", after="2025-01-01")` |
| Returns: "Dr. Smith works on epistemology..." | `find_person(name="Smith")` → structured JSON |
| Single retrieval pass | LLM can chain multiple tool calls |

Benefits:
- **Precision**: Tools return exactly what's asked
- **Structure**: Responses are typed and predictable
- **Composability**: LLM can combine tool results
- **Debuggability**: Tool calls are inspectable

### MCP Server Template
- status: active
- type: task
- id: rags-agent.mcp.template
- priority: medium
- estimate: 2h
<!-- content -->
A template for building an MCP server that exposes your data as queryable tools.

```python
"""
MCP Server Template for RAG Data Access

This template shows how to expose structured data as MCP tools.
Customize the tools and data loading for your specific use case.

Run with: python -m mcp_server.data_server
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("data-server")
DATA_DIR = Path(__file__).parent.parent / "data"


def load_data(filename: str) -> list[dict]:
    """Load JSON data from the data directory."""
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return []


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Define the tools available to the LLM."""
    return [
        Tool(
            name="search_documents",
            description="Search documents by keyword or topic. Returns matching excerpts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keywords or topic)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_by_date_range",
            description="Get items within a date range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO format: YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO format: YYYY-MM-DD)"
                    },
                    "item_type": {
                        "type": "string",
                        "description": "Type of item to filter (optional)"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="get_entity_details",
            description="Get detailed information about a specific entity by name or ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Name or ID of the entity"
                    }
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="list_categories",
            description="List all available categories or types in the data.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the LLM."""
    
    if name == "search_documents":
        query = arguments.get("query", "").lower()
        limit = arguments.get("limit", 5)
        
        # Load and search your data
        documents = load_data("documents.json")
        
        matches = []
        for doc in documents:
            searchable = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
            if query in searchable:
                matches.append(doc)
        
        if not matches:
            return [TextContent(type="text", text=f"No documents found for '{query}'.")]
        
        result = f"Found {len(matches)} documents:\n\n"
        for doc in matches[:limit]:
            result += f"**{doc.get('title', 'Untitled')}**\n"
            result += f"{doc.get('content', '')[:200]}...\n\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "get_by_date_range":
        start = arguments.get("start_date")
        end = arguments.get("end_date")
        item_type = arguments.get("item_type")
        
        items = load_data("items.json")
        
        filtered = []
        for item in items:
            item_date = item.get("date", "")
            if start <= item_date <= end:
                if item_type is None or item.get("type") == item_type:
                    filtered.append(item)
        
        if not filtered:
            return [TextContent(type="text", text=f"No items found between {start} and {end}.")]
        
        result = f"Items from {start} to {end}:\n\n"
        for item in sorted(filtered, key=lambda x: x.get("date", "")):
            result += f"- [{item.get('date')}] {item.get('title', 'Untitled')}\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "get_entity_details":
        identifier = arguments.get("identifier", "").lower()
        
        entities = load_data("entities.json")
        
        for entity in entities:
            if identifier in entity.get("name", "").lower() or identifier == entity.get("id", ""):
                result = f"**{entity.get('name', 'Unknown')}**\n\n"
                for key, value in entity.items():
                    if key not in ["name", "id"]:
                        result += f"- **{key}**: {value}\n"
                return [TextContent(type="text", text=result)]
        
        return [TextContent(type="text", text=f"No entity found matching '{identifier}'.")]
    
    elif name == "list_categories":
        items = load_data("items.json")
        categories = set(item.get("type", "unknown") for item in items)
        
        result = "Available categories:\n"
        for cat in sorted(categories):
            count = sum(1 for item in items if item.get("type") == cat)
            result += f"- {cat} ({count} items)\n"
        
        return [TextContent(type="text", text=result)]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="data-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Lightweight Tool Integration
- status: active
- type: task
- id: rags-agent.mcp.lightweight
- priority: high
- estimate: 30m
<!-- content -->
If full MCP setup is too heavy, use a lightweight tool-calling pattern within your existing code.

```python
class LightweightToolRunner:
    """
    Lightweight tool runner for RAG enhancement.
    
    Exposes data as callable tools without full MCP infrastructure.
    The LLM uses a simple text protocol to request tool calls.
    """
    
    def __init__(self, data_dir: str):
        """
        Initialize with path to data directory.
        
        Args:
            data_dir: Directory containing JSON data files
        """
        self.data_dir = data_dir
        self._cache = {}
    
    def _load(self, filename: str) -> list[dict]:
        """Load and cache JSON data."""
        if filename not in self._cache:
            filepath = f"{self.data_dir}/{filename}"
            try:
                with open(filepath, 'r') as f:
                    self._cache[filename] = json.load(f)
            except FileNotFoundError:
                self._cache[filename] = []
        return self._cache[filename]
    
    def get_tool_descriptions(self) -> str:
        """
        Returns tool descriptions for inclusion in LLM prompt.
        """
        return """Available tools:
- search(query): Search all data by keyword
- get_recent(days): Get items from the last N days
- lookup(name): Get details about a specific entity
- list_types(): List all item types/categories

To use a tool, respond with:
TOOL: tool_name
ARGS: {"param": "value"}"""
    
    def execute(self, tool_name: str, args: dict) -> str:
        """
        Execute a tool and return results as string.
        
        Args:
            tool_name: Name of tool to execute
            args: Tool arguments as dict
        
        Returns:
            Formatted string result
        """
        if tool_name == "search":
            query = args.get("query", "").lower()
            all_data = self._load("data.json")
            
            matches = [
                item for item in all_data
                if query in json.dumps(item).lower()
            ]
            
            if not matches:
                return f"No results for '{query}'."
            
            return "\n".join(
                f"- {item.get('title', item.get('name', 'Item'))}"
                for item in matches[:10]
            )
        
        elif tool_name == "get_recent":
            days = int(args.get("days", 7))
            all_data = self._load("data.json")
            
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()[:10]
            recent = [
                item for item in all_data
                if item.get("date", "") >= cutoff
            ]
            
            return "\n".join(
                f"- [{item.get('date')}] {item.get('title', 'Item')}"
                for item in sorted(recent, key=lambda x: x.get("date", ""))
            )
        
        elif tool_name == "lookup":
            name = args.get("name", "").lower()
            all_data = self._load("data.json")
            
            for item in all_data:
                if name in item.get("name", "").lower():
                    return json.dumps(item, indent=2)
            
            return f"No entity found matching '{name}'."
        
        elif tool_name == "list_types":
            all_data = self._load("data.json")
            types = set(item.get("type", "unknown") for item in all_data)
            return "Types: " + ", ".join(sorted(types))
        
        return f"Unknown tool: {tool_name}"


def parse_tool_call(text: str) -> tuple[str, dict] | None:
    """
    Parse a tool call from LLM output.
    
    Expected format:
    TOOL: tool_name
    ARGS: {"param": "value"}
    
    Args:
        text: LLM response text
    
    Returns:
        Tuple of (tool_name, args) or None if no tool call found
    """
    lines = text.strip().split('\n')
    
    tool_name = None
    args = {}
    
    for i, line in enumerate(lines):
        if line.strip().startswith("TOOL:"):
            tool_name = line.replace("TOOL:", "").strip()
        elif line.strip().startswith("ARGS:"):
            args_str = line.replace("ARGS:", "").strip()
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                pass
    
    if tool_name:
        return (tool_name, args)
    return None
```

## Cost Optimization
- status: active
- type: plan
- id: rags-agent.cost
<!-- content -->
Strategies to minimize API costs while maintaining quality.

### Caching Strategies
- status: active
- type: task
- id: rags-agent.cost.caching
- priority: high
- estimate: 30m
<!-- content -->
Cache expensive operations to avoid redundant API calls.

```python
import hashlib
import json
from pathlib import Path
from typing import Optional, Any

class RAGCache:
    """
    Simple disk-based cache for RAG operations.
    
    Caches:
    - Query decompositions
    - Step-back questions
    - Embeddings
    - Full responses (for repeated questions)
    """
    
    def __init__(self, cache_dir: str = ".rag_cache"):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _hash_key(self, key: str) -> str:
        """Generate a filesystem-safe hash for a cache key."""
        return hashlib.md5(key.encode()).hexdigest()
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Retrieve a cached value.
        
        Args:
            namespace: Cache namespace (e.g., 'decomposition', 'stepback')
            key: Cache key (usually the input query)
        
        Returns:
            Cached value or None if not found
        """
        cache_file = self.cache_dir / namespace / f"{self._hash_key(key)}.json"
        
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None
    
    def set(self, namespace: str, key: str, value: Any) -> None:
        """
        Store a value in cache.
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        namespace_dir = self.cache_dir / namespace
        namespace_dir.mkdir(exist_ok=True)
        
        cache_file = namespace_dir / f"{self._hash_key(key)}.json"
        with open(cache_file, 'w') as f:
            json.dump(value, f)
    
    def cached_decompose(self, question: str, llm_client) -> list[str]:
        """
        Query decomposition with caching.
        
        Args:
            question: Question to decompose
            llm_client: LLM client (only called on cache miss)
        
        Returns:
            List of sub-queries
        """
        cached = self.get("decomposition", question)
        if cached:
            return cached
        
        # Cache miss - call LLM
        prompt = f"""Break this into 1-3 search queries:
"{question}"
Return ONLY queries, one per line."""
        
        response = llm_client.generate_content(prompt)
        queries = [q.strip() for q in response.text.split('\n') if q.strip()]
        
        if question not in queries:
            queries.insert(0, question)
        queries = queries[:4]
        
        self.set("decomposition", question, queries)
        return queries
```

### Model Tiering
- status: active
- type: guideline
- id: rags-agent.cost.tiering
- priority: medium
<!-- content -->
Use cheaper models for simple tasks, expensive models only for final generation.

| Task | Recommended Model | Rationale |
|:-----|:------------------|:----------|
| Query decomposition | `gemini-1.5-flash` / `gpt-4o-mini` | Simple task, cheap model sufficient |
| Step-back generation | `gemini-1.5-flash` / `gpt-4o-mini` | Simple task |
| Self-ask decisions | `gemini-1.5-flash` / `gpt-4o-mini` | Binary decision |
| Final answer | `gemini-1.5-pro` / `gpt-4o` / `claude-sonnet` | Quality matters here |
| Reranking | Local cross-encoder | No API cost |

**Implementation tip**: Pass different client instances for different operations:

```python
class TieredRAGEngine:
    """RAG engine using model tiering for cost optimization."""
    
    def __init__(self, cheap_client, expensive_client, vector_store):
        """
        Initialize with two LLM clients.
        
        Args:
            cheap_client: Fast/cheap model for simple tasks
            expensive_client: Quality model for final generation
            vector_store: Vector database
        """
        self.cheap = cheap_client
        self.expensive = expensive_client
        self.vector_store = vector_store
    
    def answer(self, question: str) -> str:
        # Use cheap model for decomposition
        decomp_prompt = f'Break into search queries: "{question}"'
        queries = self.cheap.generate_content(decomp_prompt).text.split('\n')
        
        # Retrieve context
        context = []
        for q in queries[:3]:
            results = self.vector_store.query(query_texts=[q.strip()], n_results=3)
            context.extend(results['documents'][0])
        
        # Use expensive model for final answer
        final_prompt = f"""Answer: {question}

Context:
{chr(10).join(context)}"""
        
        return self.expensive.generate_content(final_prompt).text
```

## Evaluation Framework
- status: active
- type: plan
- id: rags-agent.evaluation
<!-- content -->
Measure RAG performance to guide optimization efforts.

### Key Metrics
- status: active
- type: guideline
- id: rags-agent.evaluation.metrics
<!-- content -->
Track these metrics to evaluate RAG quality:

| Metric | What It Measures | How to Compute |
|:-------|:-----------------|:---------------|
| **Retrieval Recall** | % of relevant docs retrieved | Manual annotation of test set |
| **Retrieval Precision** | % of retrieved docs that are relevant | Manual annotation |
| **Answer Correctness** | Is the final answer correct? | Compare to gold answers |
| **Faithfulness** | Is the answer grounded in context? | Check claims against retrieved docs |
| **Latency** | End-to-end response time | Timing measurement |
| **Cost per Query** | API costs per query | Sum of LLM calls × token prices |

### Simple Evaluation Script
- status: active
- type: task
- id: rags-agent.evaluation.script
- priority: low
- estimate: 1h
<!-- content -->
```python
"""
Simple RAG evaluation framework.

Create a test set of questions with expected answers,
then measure how well your RAG system performs.
"""

import json
import time
from typing import Callable
from dataclasses import dataclass

@dataclass
class TestCase:
    """A single test case for RAG evaluation."""
    question: str
    expected_answer: str
    relevant_doc_ids: list[str]  # IDs of docs that should be retrieved

@dataclass  
class EvalResult:
    """Results from evaluating a single test case."""
    question: str
    retrieved_ids: list[str]
    generated_answer: str
    retrieval_recall: float
    retrieval_precision: float
    answer_correct: bool  # Requires manual check or LLM judge
    latency_ms: float


def evaluate_rag(
    test_cases: list[TestCase],
    rag_function: Callable[[str], tuple[str, list[str]]],  # Returns (answer, retrieved_ids)
    judge_function: Callable[[str, str, str], bool] = None  # (question, expected, actual) -> correct
) -> list[EvalResult]:
    """
    Evaluate a RAG system on a test set.
    
    Args:
        test_cases: List of test cases
        rag_function: RAG system to evaluate
        judge_function: Optional LLM judge for correctness
    
    Returns:
        List of evaluation results
    """
    results = []
    
    for tc in test_cases:
        start = time.time()
        answer, retrieved_ids = rag_function(tc.question)
        latency = (time.time() - start) * 1000
        
        # Compute retrieval metrics
        retrieved_set = set(retrieved_ids)
        relevant_set = set(tc.relevant_doc_ids)
        
        true_positives = len(retrieved_set & relevant_set)
        recall = true_positives / len(relevant_set) if relevant_set else 1.0
        precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
        
        # Judge answer correctness
        correct = False
        if judge_function:
            correct = judge_function(tc.question, tc.expected_answer, answer)
        
        results.append(EvalResult(
            question=tc.question,
            retrieved_ids=retrieved_ids,
            generated_answer=answer,
            retrieval_recall=recall,
            retrieval_precision=precision,
            answer_correct=correct,
            latency_ms=latency
        ))
    
    return results


def print_eval_summary(results: list[EvalResult]) -> None:
    """Print summary statistics from evaluation."""
    n = len(results)
    
    avg_recall = sum(r.retrieval_recall for r in results) / n
    avg_precision = sum(r.retrieval_precision for r in results) / n
    avg_latency = sum(r.latency_ms for r in results) / n
    accuracy = sum(r.answer_correct for r in results) / n
    
    print(f"=== RAG Evaluation Summary ({n} test cases) ===")
    print(f"Retrieval Recall:    {avg_recall:.2%}")
    print(f"Retrieval Precision: {avg_precision:.2%}")
    print(f"Answer Accuracy:     {accuracy:.2%}")
    print(f"Avg Latency:         {avg_latency:.0f}ms")
```

## Quick Reference
- status: active
- type: guideline
- id: rags-agent.quickref
<!-- content -->
Decision matrix for choosing improvements:

| If You Have... | Try First | Then Try |
|:---------------|:----------|:---------|
| Bad recall (missing relevant docs) | Query Decomposition | Hybrid Search |
| Bad precision (too much noise) | Reranking | Reduce top-k |
| Multi-part questions | Query Decomposition | Self-Ask |
| Specific terminology | Hybrid Search | Better chunking |
| Hallucinations | Verify-Then-Answer | Stronger grounding prompt |
| High costs | Caching, Model Tiering | Reduce iterations |
| Structured data | MCP Tools | Lightweight Tool Runner |

**Cost-quality tradeoffs**:

| Strategy | Quality Gain | Cost Increase |
|:---------|:-------------|:--------------|
| Query Decomposition | +15-25% recall | +5-10% |
| Step-Back Prompting | +10-20% recall | +5-10% |
| Hybrid Search | +10-15% recall | +0% (compute only) |
| Reranking | +10-20% precision | +0% (local model) |
| Self-Ask (2 iter) | +20-30% complex Q | +30-50% |
| MCP Tools | +25-40% structured | +30-50% |
| Caching | - | -20-50% |
| Model Tiering | - | -30-60% |
