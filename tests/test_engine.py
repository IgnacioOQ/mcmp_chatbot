import pytest
from unittest.mock import MagicMock, patch
from src.core.engine import RAGEngine

@pytest.fixture
def mock_vector_store():
    with patch('src.core.engine.VectorStore') as mock_vs_cls:
        mock_vs_instance = MagicMock()
        mock_vs_cls.return_value = mock_vs_instance
        yield mock_vs_instance

@pytest.fixture
def engine(mock_vector_store):
    # Initialize with a dummy key to bypass the environment check error
    return RAGEngine(provider="openai", api_key="dummy-key")

def test_decompose_query_no_decomposition(engine):
    # Test fallback
    # Mock openai client
    with patch('src.core.engine.openai.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = "Query 1\nQuery 2"
        
        queries = engine.decompose_query("Complex question")
        assert len(queries) >= 2
        assert "Query 1" in queries

def test_retrieve_with_decomposition(engine, mock_vector_store):
    # Mock decompose
    engine.decompose_query = MagicMock(return_value=["q1", "q2"])
    
    # Mock vector store query results
    # Structure: {'ids': [['id1']], 'documents': [['doc1']], 'metadatas': [[{'url': 'u1'}]]}
    mock_vector_store.query.return_value = {
        'ids': [['id1']], 
        'documents': [['doc1']], 
        'metadatas': [[{'url': 'u1'}]]
    }
    
    chunks = engine.retrieve_with_decomposition("Question")
    
    # Should be called twice (for q1 and q2)
    assert mock_vector_store.query.call_count == 2
    # Should deduplicate if same id returned
    assert len(chunks) == 1 
    assert chunks[0]['text'] == 'doc1'

def test_generate_response_openai(engine):
    with patch('src.core.engine.openai.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = "The answer is logic."
        
        # Mock retrieval to avoid real DB usage
        engine.retrieve_with_decomposition = MagicMock(return_value=[
            {'text': 'Context info', 'metadata': {'url': 'http://test'}}
        ])
        
        response = engine.generate_response("What is the answer?")
        assert "The answer is logic" in response
