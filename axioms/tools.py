"""External tools the agent can call.

The Foundation MVP had no tool use: it trusted whatever verification status the
caller asserted. This module gives the agent a real capability -- checking a
DOI against Crossref, an authoritative bibliographic registry -- so that
metadata verification is grounded in an external source of truth rather than in
the caller's word.

The HTTP transport is injectable. In production :class:`CrossrefClient` calls
the live API over ``urllib``; in tests a fake ``fetch`` returns canned records,
so the whole tool layer is exercised deterministically and offline.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from urllib.request import Request, urlopen

CROSSREF_WORKS_URL = "https://api.crossref.org/works/"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Crossref work types that are not peer-reviewed publications on their own.
PREPRINT_TYPES = {"posted-content", "preprint"}

# fetch(url) -> parsed JSON object. Injected so the network can be faked in tests.
Fetch = Callable[[str], dict]
TavilyFetch = Callable[[str, dict], dict]


class CrossrefError(RuntimeError):
    """Raised when a DOI cannot be resolved or the response is unusable."""


class TavilyError(RuntimeError):
    """Raised when controlled evidence discovery cannot complete safely."""


@dataclass(frozen=True, slots=True)
class CrossrefRecord:
    """Canonical metadata for one work, as reported by Crossref."""

    doi: str
    title: str | None
    authors: tuple[str, ...]
    year: int | None
    work_type: str | None
    is_preprint: bool

    def summary(self) -> str:
        author = self.authors[0] if self.authors else "unknown author"
        return f"Crossref: {author} ({self.year}) — {self.title} [{self.work_type}]"


def _default_fetch(url: str, *, timeout: float = 15.0, mailto: str | None = None) -> dict:
    """Real transport. Crossref etiquette asks callers to identify themselves."""

    contact = f"; mailto:{mailto}" if mailto else ""
    request = Request(url, headers={"User-Agent": f"AxiomsAISystem/0.2 (+https://github.com/DrAslamJaved){contact}"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _default_tavily_fetch(url: str, payload: dict, *, timeout: float = 20.0) -> dict:
    """Read-only Tavily search transport; callers never receive a write capability."""

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AxiomsAISystem/0.2"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class CrossrefClient:
    """Looks up DOIs against Crossref and normalises the result."""

    def __init__(self, fetch: Fetch | None = None, *, mailto: str | None = None) -> None:
        self._mailto = mailto
        self._fetch = fetch or (lambda url: _default_fetch(url, mailto=mailto))

    def lookup(self, doi: str) -> CrossrefRecord:
        normalized = doi.strip()
        normalized = normalized.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        if not normalized:
            raise CrossrefError("An empty DOI cannot be looked up.")
        url = CROSSREF_WORKS_URL + quote(normalized, safe="")
        try:
            payload = self._fetch(url)
        except CrossrefError:
            raise
        except Exception as error:  # network, decode, timeout -- surfaced as one tool error
            raise CrossrefError(f"Crossref lookup failed for {normalized}: {error}") from error
        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, dict):
            raise CrossrefError(f"Crossref returned no work record for {normalized}.")
        return _record_from_message(normalized, message)


@dataclass(frozen=True, slots=True)
class DiscoveredSource:
    """A search candidate, never a verified claim or an approved citation."""

    title: str
    url: str
    snippet: str
    score: float | None
    published_date: str | None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    query: str
    sources: tuple[DiscoveredSource, ...]
    retrieved_at: str
    provenance: str = "Tavily read-only web discovery"
    verification_boundary: str = (
        "Search results are unverified candidates. Verify source metadata and each claim before "
        "citation, synthesis, or external use."
    )

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "sources": [
                {
                    "title": source.title,
                    "url": source.url,
                    "snippet": source.snippet,
                    "score": source.score,
                    "published_date": source.published_date,
                }
                for source in self.sources
            ],
            "retrieved_at": self.retrieved_at,
            "provenance": self.provenance,
            "verification_boundary": self.verification_boundary,
        }


class TavilyClient:
    """Bounded read-only evidence discovery backed by Tavily's search API."""

    def __init__(self, api_key: str | None, fetch: TavilyFetch | None = None) -> None:
        self._api_key = (api_key or "").strip()
        self._fetch = fetch or _default_tavily_fetch

    def discover(self, query: str, *, max_results: int = 5) -> DiscoveryResult:
        normalized_query = query.strip()
        if len(normalized_query) < 8:
            raise TavilyError("Research discovery requires a query of at least 8 characters.")
        if not 1 <= max_results <= 10:
            raise TavilyError("max_results must be between 1 and 10.")
        if not self._api_key:
            raise TavilyError("Tavily is not configured. Set TAVILY_API_KEY to enable read-only discovery.")
        payload = {
            "api_key": self._api_key,
            "query": normalized_query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "topic": "general",
        }
        try:
            response = self._fetch(TAVILY_SEARCH_URL, payload)
        except TavilyError:
            raise
        except Exception as error:
            raise TavilyError(f"Tavily discovery failed: {error}") from error
        rows = response.get("results") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            raise TavilyError("Tavily returned no usable search-result list.")
        sources = tuple(_discovered_source(row) for row in rows if _is_usable_source(row))
        return DiscoveryResult(
            query=normalized_query,
            sources=sources[:max_results],
            retrieved_at=datetime.now(UTC).isoformat(),
        )


def _is_usable_source(row: object) -> bool:
    return isinstance(row, dict) and bool(str(row.get("title") or "").strip()) and str(
        row.get("url") or ""
    ).startswith("https://")


def _discovered_source(row: object) -> DiscoveredSource:
    assert isinstance(row, dict)
    raw_score = row.get("score")
    score = float(raw_score) if isinstance(raw_score, (int, float)) else None
    return DiscoveredSource(
        title=str(row["title"]).strip(),
        url=str(row["url"]).strip(),
        snippet=str(row.get("content") or "").strip(),
        score=score,
        published_date=str(row["published_date"]) if row.get("published_date") else None,
    )


def _record_from_message(doi: str, message: dict) -> CrossrefRecord:
    titles = message.get("title") or []
    title = titles[0] if isinstance(titles, list) and titles else None
    authors: list[str] = []
    for entry in message.get("author") or []:
        if not isinstance(entry, dict):
            continue
        family = (entry.get("family") or "").strip()
        given = (entry.get("given") or "").strip()
        full = " ".join(part for part in (given, family) if part).strip()
        if full:
            authors.append(full)
    work_type = message.get("type")
    year = _extract_year(message)
    return CrossrefRecord(
        doi=doi,
        title=title,
        authors=tuple(authors),
        year=year,
        work_type=work_type,
        is_preprint=work_type in PREPRINT_TYPES,
    )


def _extract_year(message: dict) -> int | None:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        block = message.get(field)
        if isinstance(block, dict):
            parts = block.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                try:
                    return int(parts[0][0])
                except (TypeError, ValueError):
                    continue
    return None


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def title_similarity(a: str | None, b: str | None) -> float:
    """Jaccard token overlap in [0, 1]. Robust to punctuation and casing."""

    if not a or not b:
        return 0.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def titles_match(a: str | None, b: str | None, *, threshold: float = 0.6) -> bool:
    return title_similarity(a, b) >= threshold
