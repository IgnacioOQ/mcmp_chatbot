import pytest
from unittest.mock import MagicMock, patch
from src.core.engine import ChatEngine

@pytest.fixture
def engine():
    # Initialize with a dummy key to bypass the environment check error
    return ChatEngine(provider="openai", api_key="dummy-key")

def test_engine_init(engine):
    """Test that ChatEngine initializes with MCP server and graph utils."""
    assert engine.mcp_server is not None
    assert engine.graph_utils is not None
    assert engine.provider == "openai"

def test_generate_response_openai(engine):
    with patch('src.core.engine.openai.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "The answer is logic."
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        
        response = engine.generate_response("What is the answer?")
        assert "The answer is logic" in response
        
        # Verify tools were passed to the API call
        call_args = mock_client.chat.completions.create.call_args
        assert "tools" in call_args.kwargs
        assert len(call_args.kwargs["tools"]) > 0
