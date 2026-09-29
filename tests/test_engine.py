import pytest
from unittest.mock import MagicMock, patch
from google.genai import types
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


# ── Gemini: forced final answer when the tool budget runs out ───────────────


def _gemini_engine():
    engine = ChatEngine(provider="gemini", api_key="dummy-key", use_mcp=False)
    engine._gemini_client = MagicMock()
    return engine


def _exhausted_response():
    """An AFC response that ended on a tool call: no text, trail ends on the call."""
    call = types.Content(role="model", parts=[types.Part.from_function_call(name="grep_data", args={"pattern": "x"})])
    resp = types.Content(role="user", parts=[types.Part.from_function_response(name="grep_data", response={"result": []})])
    response = MagicMock()
    response.text = None
    response.automatic_function_calling_history = [
        types.Content(role="user", parts=[types.Part.from_text(text="Who are the PhD contacts?")]),
        call, resp, call,
    ]
    return response


def test_generate_response_forces_final_answer_when_budget_exhausted():
    engine = _gemini_engine()
    engine._gemini_client.chats.create.return_value.send_message.return_value = _exhausted_response()
    engine._gemini_client.models.generate_content.return_value.text = "The records do not list a contact."

    assert engine.generate_response("Who are the PhD contacts?") == "The records do not list a contact."

    kwargs = engine._gemini_client.models.generate_content.call_args.kwargs
    contents = kwargs["contents"]
    # Trailing unanswered tool call dropped, answer-now instruction appended.
    assert [c.role for c in contents] == ["user", "model", "user", "user"]
    assert "Tool budget exhausted" in contents[-1].parts[0].text
    assert kwargs["config"].tool_config.function_calling_config.mode == "NONE"


def test_generate_response_returns_text_without_fallback():
    engine = _gemini_engine()
    engine._gemini_client.chats.create.return_value.send_message.return_value.text = "Hannes Leitgeb."

    assert engine.generate_response("Who leads the chair?") == "Hannes Leitgeb."
    engine._gemini_client.models.generate_content.assert_not_called()


def test_stream_falls_back_when_no_text_streamed():
    engine = _gemini_engine()
    engine._gemini_client.chats.create.return_value.send_message_stream.return_value = iter([MagicMock(text=None)])
    with patch.object(engine, "generate_response", return_value="Forced answer.") as fallback:
        assert "".join(engine.generate_response_stream("q")) == "Forced answer."
    fallback.assert_called_once()
    assert "status_callback" not in fallback.call_args.kwargs
