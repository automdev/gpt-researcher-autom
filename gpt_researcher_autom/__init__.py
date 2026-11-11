"""GPT Researcher retriever plugin for Autom (https://www.autom.dev).

Install it next to GPT Researcher and set ``RETRIEVER=autom`` and ``AUTOM_API_KEY``.
The search results are links that GPT Researcher scrapes, so ``requires_scraping`` is True.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

try:  # Subclassing is optional; it documents the contract when GPT Researcher is installed.
    from gpt_researcher.retrievers.base import BaseRetriever
except ImportError:  # pragma: no cover - GPT Researcher is always present at runtime
    BaseRetriever = object  # type: ignore[misc,assignment]

__all__ = ["AutomSearch"]
__version__ = "0.1.0"

logger = logging.getLogger(__name__)

BASE_URL = "https://api.autom.dev"
USER_AGENT = f"gpt-researcher-autom/{__version__}"
TIMEOUT = 30.0
ENGINES = ("google", "bing", "brave", "duckduckgo", "yahoo")


class AutomSearch(BaseRetriever):  # type: ignore[misc]
    """Search the web with Autom for GPT Researcher.

    Reads ``AUTOM_API_KEY``. AUTOM_ENGINE: google (default), bing, brave, duckduckgo or yahoo.
    """

    requires_scraping = True

    def __init__(self, query: str, query_domains: list[str] | None = None) -> None:
        self.query = query
        self.query_domains = [d.strip() for d in (query_domains or []) if d and d.strip()]
        self.api_key = (os.environ.get("AUTOM_API_KEY") or "").strip()
        engine = (os.environ.get("AUTOM_ENGINE") or "google").strip().lower()
        self.engine = engine if engine in ENGINES else "google"

    def _query(self) -> str:
        if not self.query_domains:
            return self.query
        sites = " OR ".join(f"site:{domain}" for domain in self.query_domains)
        return f"{self.query} ({sites})" if len(self.query_domains) > 1 else f"{self.query} {sites}"

    def search(self, max_results: int = 7) -> list[dict[str, Any]]:
        """Return up to ``max_results`` results as ``{"href", "body", "title"}`` dicts, or ``[]`` on any error."""
        if not self.api_key:
            logger.warning("AUTOM_API_KEY is not set; the Autom retriever returns no results.")
            return []
        params: dict[str, Any] = {"query": self._query()}
        headers = {"x-api-key": self.api_key, "Accept": "application/json", "User-Agent": USER_AGENT}
        try:
            response = httpx.get(f"{BASE_URL}/v1/{self.engine}/search", params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("Autom search failed%s.", f" (HTTP {status})" if status else "")
            return []
        rows = body.get("organic_results") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            return []
        results = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            link = row.get("link")
            if not isinstance(link, str) or not link.startswith(("http://", "https://")):
                continue
            results.append({"href": link, "body": str(row.get("snippet") or ""), "title": str(row.get("title") or "")})
            if len(results) >= max_results:
                break
        return results
