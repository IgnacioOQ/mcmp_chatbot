import pytest
from unittest.mock import MagicMock, patch
from src.core.engine import ChatEngine

@pytest.fixture
def engine():
    # Initialize with a dummy key to bypass the environment check error
    # We use 'gemini' as it is the default model for this repository
    with patch('google.genai.Client') as mock_genai_client:
        mock_client_instance = MagicMock()
        mock_genai_client.return_value = mock_client_instance
        engine_instance = ChatEngine(provider="gemini", api_key="dummy-key", use_mcp=False)
        # Re-attach the mocked client since ChatEngine creates it in init
        engine_instance._gemini_client = mock_client_instance
        yield engine_instance

def test_generate_response_gemini(engine):
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "The answer is logic."
    mock_chat.send_message.return_value = mock_response

    engine._gemini_client.chats.create.return_value = mock_chat

    response = engine.generate_response("What is the answer?", use_mcp_tools=False)
    assert "The answer is logic" in response
