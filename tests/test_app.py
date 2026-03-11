"""Tests for the Flask app routes and API proxy."""

import json
from http.client import HTTPResponse
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app import SEARCH_PRESETS, SYSTEM_PROMPT, app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- Index route ---


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Cayenne Finder" in resp.data


# --- Search route: validation ---


def test_search_requires_api_key(client):
    resp = client.post("/search", json={"query": "test"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "API key is required"


def test_search_requires_query(client):
    resp = client.post(
        "/search", json={"query": ""}, headers={"X-Api-Key": "sk-test"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Query is required"


def test_search_requires_query_field(client):
    resp = client.post("/search", json={}, headers={"X-Api-Key": "sk-test"})
    assert resp.status_code == 400


def test_search_whitespace_only_query(client):
    resp = client.post(
        "/search", json={"query": "   "}, headers={"X-Api-Key": "sk-test"}
    )
    assert resp.status_code == 400


# --- Search route: API proxy ---


MOCK_API_RESPONSE = {
    "id": "msg_123",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "web_search_tool_result",
            "tool_use_id": "ws_1",
            "content": [
                {
                    "type": "web_search_result",
                    "title": "2022 Cayenne on Cars.com",
                    "url": "https://www.cars.com/listing/123",
                    "encrypted_content": "...",
                }
            ],
        },
        {
            "type": "text",
            "text": "Found a 2022 Porsche Cayenne for $32,000.",
        },
    ],
    "model": "claude-sonnet-4-6",
    "stop_reason": "end_turn",
}


def _mock_urlopen(response_body, status=200):
    """Create a mock for urllib.request.urlopen that returns given response."""
    resp_bytes = json.dumps(response_body).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = resp_bytes
    mock_resp.status = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


@patch("app.urllib.request.urlopen")
def test_search_proxies_to_anthropic(mock_urlopen, client):
    mock_urlopen.return_value = _mock_urlopen(MOCK_API_RESPONSE)

    resp = client.post(
        "/search",
        json={"query": "Find Cayennes in Texas"},
        headers={"X-Api-Key": "sk-test-key"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["content"][0]["type"] == "web_search_tool_result"
    assert data["content"][1]["text"] == "Found a 2022 Porsche Cayenne for $32,000."

    # Verify the request sent to Anthropic
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert req.full_url == "https://api.anthropic.com/v1/messages"
    assert req.get_header("X-api-key") == "sk-test-key"
    assert req.get_header("Anthropic-version") == "2023-06-01"

    payload = json.loads(req.data)
    assert payload["model"] == "claude-sonnet-4-6"
    assert payload["tools"][0]["type"] == "web_search_20260209"
    assert payload["system"] == SYSTEM_PROMPT
    assert payload["messages"][0]["content"] == "Find Cayennes in Texas"


@patch("app.urllib.request.urlopen")
def test_search_forwards_api_errors(mock_urlopen, client):
    import urllib.error

    error_body = json.dumps(
        {"type": "error", "error": {"type": "authentication_error", "message": "Invalid API key"}}
    ).encode()
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO(error_body),
    )

    resp = client.post(
        "/search",
        json={"query": "test"},
        headers={"X-Api-Key": "sk-bad-key"},
    )

    assert resp.status_code == 401
    data = resp.get_json()
    assert data["error"]["type"] == "authentication_error"


@patch("app.urllib.request.urlopen")
def test_search_handles_network_errors(mock_urlopen, client):
    mock_urlopen.side_effect = ConnectionError("Connection refused")

    resp = client.post(
        "/search",
        json={"query": "test"},
        headers={"X-Api-Key": "sk-test"},
    )

    assert resp.status_code == 502
    assert "Proxy error" in resp.get_json()["error"]


# --- Payload construction ---


@patch("app.urllib.request.urlopen")
def test_payload_has_no_beta_header(mock_urlopen, client):
    mock_urlopen.return_value = _mock_urlopen(MOCK_API_RESPONSE)

    client.post(
        "/search",
        json={"query": "test"},
        headers={"X-Api-Key": "sk-test"},
    )

    req = mock_urlopen.call_args[0][0]
    assert req.get_header("Anthropic-beta") is None


@patch("app.urllib.request.urlopen")
def test_payload_uses_correct_tool_type(mock_urlopen, client):
    mock_urlopen.return_value = _mock_urlopen(MOCK_API_RESPONSE)

    client.post(
        "/search",
        json={"query": "test"},
        headers={"X-Api-Key": "sk-test"},
    )

    payload = json.loads(mock_urlopen.call_args[0][0].data)
    tool = payload["tools"][0]
    assert tool["type"] == "web_search_20260209"
    assert tool["name"] == "web_search"
    assert tool["max_uses"] == 10


# --- Presets ---


def test_presets_have_labels_and_queries():
    assert len(SEARCH_PRESETS) >= 3
    for preset in SEARCH_PRESETS:
        assert "label" in preset
        assert "query" in preset
        assert len(preset["label"]) > 0
        assert len(preset["query"]) > 0


def test_presets_mention_cayenne():
    for preset in SEARCH_PRESETS:
        assert "cayenne" in preset["query"].lower()


# --- System prompt ---


def test_system_prompt_mentions_key_sites():
    prompt = SYSTEM_PROMPT.lower()
    for site in ["cars.com", "carvana.com", "carmax.com", "autotrader.com", "cargurus.com"]:
        assert site in prompt


def test_system_prompt_mentions_feature_verification():
    prompt = SYSTEM_PROMPT.lower()
    assert "ventilated" in prompt
    assert "adaptive cruise" in prompt
    assert "panoramic" in prompt
    assert "premium plus package" in prompt
