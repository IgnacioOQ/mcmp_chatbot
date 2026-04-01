import pytest
from unittest.mock import MagicMock, patch
from src.core.engine import ChatEngine

@pytest.fixture
def engine():
    # Initialize with a dummy key to bypass the environment check error
    return ChatEngine(provider="openai", api_key="dummy-key", use_mcp=False)

def test_generate_response_openai(engine):
    with patch('src.core.engine.openai.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the API response directly without assuming tool calls
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "The answer is logic."
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=mock_message)
        ]

        response = engine.generate_response("What is the answer?", use_mcp_tools=False)
        assert "The answer is logic" in response
