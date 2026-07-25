"""OllamaProvider unit tests with a mocked daemon. The live smoke happens
in the provider matrix, not here."""

from unittest.mock import patch

from banko_ai.ai_providers.factory import AIProviderFactory


def _cfg():
    return {"host": "http://localhost:11434", "model": "granite3.3:8b"}


@patch("banko_ai.ai_providers.ollama_provider.requests.get")
def test_dynamic_model_discovery(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "models": [{"name": "granite3.3:8b"}, {"name": "llama3.2:latest"}]}
    p = AIProviderFactory.create_provider("ollama", _cfg())
    models = p.get_available_models()
    assert "granite3.3:8b" in models
    assert "llama3.2:latest" in models


@patch("banko_ai.ai_providers.ollama_provider.requests.post")
def test_chat_roundtrip(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "message": {"content": "You spent $10."}}
    p = AIProviderFactory.create_provider("ollama", _cfg())
    out = p._chat([{"role": "user", "content": "hi"}])
    assert "$10" in out


@patch("banko_ai.ai_providers.ollama_provider.requests.get")
def test_connection_failure_is_clean(mock_get):
    import requests as real_requests
    mock_get.side_effect = real_requests.exceptions.ConnectionError("boom")
    p = AIProviderFactory.create_provider("ollama", _cfg())
    assert p.test_connection() is False
