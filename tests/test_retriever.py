"""Offline tests for the autom retriever plugin (httpx.MockTransport)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib.metadata import entry_points

import httpx
import pytest

import gpt_researcher_autom as plugin
from gpt_researcher_autom import AutomSearch

API_KEY = "test-autom-key-placeholder"  # pragma: allowlist secret
ROWS = [
    {"position": 1, "title": "GPT Researcher", "link": "https://gptr.dev/", "snippet": "Autonomous research."},
    {"position": 2, "title": "No snippet", "link": "https://example.com/"},
    {"position": 3, "title": "Not a web link", "link": "ftp://example.com/"},
    "not an object",
    {"position": 4, "title": "Third", "link": "https://third.example/", "snippet": "s"},
]

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[httpx.Request]]:
    def install(handler: Handler) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        transport = httpx.MockTransport(record)

        def fake_get(url, **kwargs):
            kwargs.pop("timeout", None)
            with httpx.Client(transport=transport) as client:
                return client.get(url, **kwargs)

        monkeypatch.setattr(plugin.httpx, "get", fake_get)
        return seen

    return install


@pytest.fixture(autouse=True)
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOM_API_KEY", f" {API_KEY} ")


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"organic_results": ROWS})


def test_entry_point_is_registered() -> None:
    names = {ep.name: ep.value for ep in entry_points(group="gpt_researcher.retrievers")}
    assert names["autom"] == "gpt_researcher_autom:AutomSearch"


def test_search_returns_href_body_title(mock_http) -> None:
    seen = mock_http(ok)
    results = AutomSearch("gpt researcher").search(max_results=7)

    assert seen[0].url.path == "/v1/google/search"
    assert seen[0].url.params["query"] == "gpt researcher"
    assert seen[0].headers["x-api-key"] == API_KEY
    assert results == [
        {"href": "https://gptr.dev/", "body": "Autonomous research.", "title": "GPT Researcher"},
        {"href": "https://example.com/", "body": "", "title": "No snippet"},
        {"href": "https://third.example/", "body": "s", "title": "Third"},
    ]
    assert AutomSearch.requires_scraping is True


def test_max_results(mock_http) -> None:
    mock_http(ok)
    assert len(AutomSearch("q").search(max_results=1)) == 1


def test_query_domains(mock_http) -> None:
    seen = mock_http(ok)
    AutomSearch("q", query_domains=["a.com", " b.com ", ""]).search()
    AutomSearch("q", query_domains=["a.com"]).search()
    assert seen[0].url.params["query"] == "q (site:a.com OR site:b.com)"
    assert seen[1].url.params["query"] == "q site:a.com"


def test_missing_key_returns_nothing(mock_http, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    monkeypatch.delenv("AUTOM_API_KEY")
    seen = mock_http(ok)
    with caplog.at_level(logging.WARNING):
        assert AutomSearch("q").search() == []
    assert seen == [] and "AUTOM_API_KEY" in caplog.text


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": "Invalid API key"}),
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json=["x"]),
        httpx.Response(200, json={"organic_results": "x"}),
        httpx.Response(200, json={}),
    ],
)
def test_errors_return_nothing_and_never_log_the_key(mock_http, response, caplog) -> None:
    mock_http(lambda request: response)
    with caplog.at_level(logging.WARNING):
        assert AutomSearch("q").search() == []
    assert API_KEY not in caplog.text


def test_network_error(mock_http, caplog) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused {API_KEY}", request=request)

    mock_http(down)
    with caplog.at_level(logging.WARNING):
        assert AutomSearch("q").search() == []
    assert API_KEY not in caplog.text


def test_engine_from_env(mock_http, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOM_ENGINE", "Brave")
    seen = mock_http(ok)
    AutomSearch("q").search()
    assert seen[0].url.path == "/v1/brave/search"


def test_unknown_engine_falls_back_to_google(mock_http, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOM_ENGINE", "altavista")
    seen = mock_http(ok)
    AutomSearch("q").search()
    assert seen[0].url.path == "/v1/google/search"
