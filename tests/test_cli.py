"""Tests for the CLI tool."""

import json
from unittest.mock import patch

import pytest

from cli import extract_sources, extract_text


# --- extract_text ---


def test_extract_text_from_response():
    data = {
        "content": [
            {"type": "web_search_tool_result", "content": []},
            {"type": "text", "text": "First result"},
            {"type": "text", "text": "Second result"},
        ]
    }
    assert extract_text(data) == "First result\n\nSecond result"


def test_extract_text_empty_content():
    assert extract_text({"content": []}) == ""
    assert extract_text({}) == ""


def test_extract_text_no_text_blocks():
    data = {"content": [{"type": "web_search_tool_result", "content": []}]}
    assert extract_text(data) == ""


# --- extract_sources ---


def test_extract_sources_from_web_search_result():
    data = {
        "content": [
            {
                "type": "web_search_tool_result",
                "content": [
                    {"type": "web_search_result", "title": "Cars.com", "url": "https://cars.com/123"},
                    {"type": "web_search_result", "title": "CarMax", "url": "https://carmax.com/456"},
                ],
            }
        ]
    }
    sources = extract_sources(data)
    assert len(sources) == 2
    assert sources[0] == {"title": "Cars.com", "url": "https://cars.com/123"}
    assert sources[1] == {"title": "CarMax", "url": "https://carmax.com/456"}


def test_extract_sources_from_server_tool_use():
    data = {
        "content": [
            {
                "type": "server_tool_use",
                "content": [
                    {"type": "web_search_result", "title": "Test", "url": "https://example.com"},
                ],
            }
        ]
    }
    sources = extract_sources(data)
    assert len(sources) == 1


def test_extract_sources_empty():
    assert extract_sources({"content": []}) == []
    assert extract_sources({}) == []


# --- CLI argument parsing ---


def test_list_presets(capsys):
    from cli import list_presets

    list_presets()
    out = capsys.readouterr().out
    assert "Base Cayenne" in out
    assert "E-Hybrid" in out


def test_main_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from cli import main

    with patch("sys.argv", ["cli.py", "test query"]):
        with pytest.raises(SystemExit, match="1"):
            main()


def test_main_list_presets(monkeypatch):
    import sys
    from cli import main

    with patch("sys.argv", ["cli.py", "--list-presets"]):
        main()  # should not raise
