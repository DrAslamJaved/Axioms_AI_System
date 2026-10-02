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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import monotonic
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

CROSSREF_WORKS_URL = "https://api.crossref.org/works/"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
ARXIV_QUERY_URL = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Crossref work types that are not peer-reviewed publications on their own.
PREPRINT_TYPES = {"posted-content", "preprint"}

# fetch(url) -> parsed JSON object. Injected so the network can be faked in tests.
Fetch = Callable[[str], dict]
TavilyFetch = Callable[[str, dict], dict]
ArxivFetch = Callable[[str], str]
SemanticScholarFetch = Callable[[str, dict[str, str]], dict]


class CrossrefError(RuntimeError):
    """Raised when a DOI cannot be resolved or the response is unusable."""


class TavilyError(RuntimeError):
    """Raised when controlled evidence discovery cannot complete safely."""


class ArxivError(RuntimeError):
    """Raised when bounded arXiv discovery cannot complete safely."""


class SemanticScholarError(RuntimeError):
    """Raised when controlled Semantic Scholar discovery cannot complete safely."""


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


def _default_arxiv_fetch(url: str, *, timeout: float = 20.0) -> str:
    """Read-only arXiv Atom API transport for a fixed HTTPS endpoint."""

    request = Request(url, headers={"User-Agent": "AxiomsAISystem/0.2 (research discovery)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _default_semantic_scholar_fetch(
    url: str, headers: dict[str, str], *, timeout: float = 20.0
) -> dict:
    """Read-only Semantic Scholar Academic Graph API transport."""

    request = Request(url, headers=headers)
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


@dataclass(frozen=True, slots=True)
class ArxivCandidate:
    """A preprint candidate returned by arXiv; never a verified research claim."""

    arxiv_id: str
    title: str
    authors: tuple[str, ...]
    abstract_url: str
    summary: str
    published: str | None
    updated: str | None
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArxivDiscoveryResult:
    query: str
    candidates: tuple[ArxivCandidate, ...]
    retrieved_at: str
    cached: bool = False
    provenance: str = "arXiv Atom API read-only preprint discovery"
    verification_boundary: str = (
        "arXiv records are preprint candidates, not peer-reviewed sources or verified claims. "
        "Verify metadata, publication status, and each claim before citation, synthesis, or external use."
    )

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "candidates": [
                {
                    "arxiv_id": candidate.arxiv_id,
                    "title": candidate.title,
                    "authors": list(candidate.authors),
                    "abstract_url": candidate.abstract_url,
                    "summary": candidate.summary,
                    "published": candidate.published,
                    "updated": candidate.updated,
                    "categories": list(candidate.categories),
                }
                for candidate in self.candidates
            ],
            "retrieved_at": self.retrieved_at,
            "cached": self.cached,
            "provenance": self.provenance,
            "verification_boundary": self.verification_boundary,
        }


class ArxivClient:
    """Bounded read-only preprint discovery with a small in-process cache and rate gate."""

    def __init__(
        self,
        fetch: ArxivFetch | None = None,
        *,
        clock: Callable[[], float] = monotonic,
        min_interval_seconds: float = 3.0,
    ) -> None:
        self._fetch = fetch or _default_arxiv_fetch
        self._clock = clock
        self._min_interval_seconds = min_interval_seconds
        self._last_live_request_at: float | None = None
        self._cache: dict[tuple[str, int], ArxivDiscoveryResult] = {}

    def discover(self, query: str, *, max_results: int = 5) -> ArxivDiscoveryResult:
        normalized_query = query.strip()
        if len(normalized_query) < 8:
            raise ArxivError("arXiv discovery requires a query of at least 8 characters.")
        if not 1 <= max_results <= 10:
            raise ArxivError("max_results must be between 1 and 10.")
        cache_key = (normalized_query.casefold(), max_results)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return replace(cached, cached=True)
        now = self._clock()
        if self._last_live_request_at is not None:
            elapsed = now - self._last_live_request_at
            if elapsed < self._min_interval_seconds:
                wait = self._min_interval_seconds - elapsed
                raise ArxivError(f"arXiv discovery is rate limited; retry after {wait:.1f} seconds.")
        params = {
            "search_query": f'all:"{normalized_query}"',
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_QUERY_URL}?{urlencode(params)}"
        try:
            response = self._fetch(url)
        except ArxivError:
            raise
        except Exception as error:
            raise ArxivError(f"arXiv discovery failed: {error}") from error
        self._last_live_request_at = now
        candidates = _arxiv_candidates(response)
        result = ArxivDiscoveryResult(
            query=normalized_query,
            candidates=candidates[:max_results],
            retrieved_at=datetime.now(UTC).isoformat(),
        )
        self._cache[cache_key] = result
        return result


@dataclass(frozen=True, slots=True)
class SemanticScholarCandidate:
    """A bibliographic candidate; Semantic Scholar metadata does not verify its claims."""

    paper_id: str
    title: str
    authors: tuple[str, ...]
    url: str | None
    abstract: str | None
    year: int | None
    venue: str | None
    doi: str | None
    publication_types: tuple[str, ...]
    citation_count: int | None


@dataclass(frozen=True, slots=True)
class SemanticScholarDiscoveryResult:
    query: str
    candidates: tuple[SemanticScholarCandidate, ...]
    retrieved_at: str
    cached: bool = False
    provenance: str = "Semantic Scholar Academic Graph API read-only discovery"
    verification_boundary: str = (
        "Semantic Scholar records are unverified bibliographic candidates. Metadata, publication "
        "status, citations, and every claim must be independently checked before citation, synthesis, or external use."
    )

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "candidates": [
                {
                    "paper_id": candidate.paper_id,
                    "title": candidate.title,
                    "authors": list(candidate.authors),
                    "url": candidate.url,
                    "abstract": candidate.abstract,
                    "year": candidate.year,
                    "venue": candidate.venue,
                    "doi": candidate.doi,
                    "publication_types": list(candidate.publication_types),
                    "citation_count": candidate.citation_count,
                }
                for candidate in self.candidates
            ],
            "retrieved_at": self.retrieved_at,
            "cached": self.cached,
            "provenance": self.provenance,
            "verification_boundary": self.verification_boundary,
        }


class SemanticScholarClient:
    """Bounded, keyed, read-only Semantic Scholar discovery with cache and rate gate."""

    def __init__(
        self,
        api_key: str | None,
        fetch: SemanticScholarFetch | None = None,
        *,
        clock: Callable[[], float] = monotonic,
        min_interval_seconds: float = 3.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._fetch = fetch or _default_semantic_scholar_fetch
        self._clock = clock
        self._min_interval_seconds = min_interval_seconds
        self._last_live_request_at: float | None = None
        self._cache: dict[tuple[str, int], SemanticScholarDiscoveryResult] = {}

    def discover(self, query: str, *, max_results: int = 5) -> SemanticScholarDiscoveryResult:
        normalized_query = query.strip()
        if len(normalized_query) < 8:
            raise SemanticScholarError("Semantic Scholar discovery requires a query of at least 8 characters.")
        if not 1 <= max_results <= 10:
            raise SemanticScholarError("max_results must be between 1 and 10.")
        if not self._api_key:
            raise SemanticScholarError(
                "Semantic Scholar is not configured. Set SEMANTIC_SCHOLAR_API_KEY to enable read-only discovery."
            )
        cache_key = (normalized_query.casefold(), max_results)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return replace(cached, cached=True)
        now = self._clock()
        if self._last_live_request_at is not None:
            elapsed = now - self._last_live_request_at
            if elapsed < self._min_interval_seconds:
                wait = self._min_interval_seconds - elapsed
                raise SemanticScholarError(
                    f"Semantic Scholar discovery is rate limited; retry after {wait:.1f} seconds."
                )
        fields = "paperId,title,authors,url,abstract,year,venue,externalIds,publicationTypes,citationCount"
        url = f"{SEMANTIC_SCHOLAR_SEARCH_URL}?{urlencode({'query': normalized_query, 'limit': max_results, 'fields': fields})}"
        headers = {"User-Agent": "AxiomsAISystem/0.2 (research discovery)", "x-api-key": self._api_key}
        try:
            response = self._fetch(url, headers)
        except SemanticScholarError:
            raise
        except Exception as error:
            raise SemanticScholarError(f"Semantic Scholar discovery failed: {error}") from error
        self._last_live_request_at = now
        rows = response.get("data") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            raise SemanticScholarError("Semantic Scholar returned no usable paper-result list.")
        result = SemanticScholarDiscoveryResult(
            query=normalized_query,
            candidates=tuple(_semantic_scholar_candidate(row) for row in rows if _is_semantic_scholar_candidate(row)),
            retrieved_at=datetime.now(UTC).isoformat(),
        )
        self._cache[cache_key] = result
        return result


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


def _is_semantic_scholar_candidate(row: object) -> bool:
    return isinstance(row, dict) and bool(str(row.get("paperId") or "").strip()) and bool(
        str(row.get("title") or "").strip()
    )


def _semantic_scholar_candidate(row: object) -> SemanticScholarCandidate:
    assert isinstance(row, dict)
    authors = tuple(
        str(author.get("name") or "").strip()
        for author in row.get("authors") or []
        if isinstance(author, dict) and str(author.get("name") or "").strip()
    )
    publication_types = tuple(
        str(publication_type).strip()
        for publication_type in row.get("publicationTypes") or []
        if str(publication_type).strip()
    )
    external_ids = row.get("externalIds")
    doi = (
        str(external_ids.get("DOI")).strip()
        if isinstance(external_ids, dict) and external_ids.get("DOI")
        else None
    )
    raw_year = row.get("year")
    raw_citation_count = row.get("citationCount")
    return SemanticScholarCandidate(
        paper_id=str(row["paperId"]).strip(),
        title=str(row["title"]).strip(),
        authors=authors,
        url=str(row["url"]).strip() if row.get("url") else None,
        abstract=str(row["abstract"]).strip() if row.get("abstract") else None,
        year=raw_year if isinstance(raw_year, int) else None,
        venue=str(row["venue"]).strip() if row.get("venue") else None,
        doi=doi,
        publication_types=publication_types,
        citation_count=raw_citation_count if isinstance(raw_citation_count, int) else None,
    )


def _arxiv_candidates(xml: str) -> tuple[ArxivCandidate, ...]:
    if not isinstance(xml, str) or not xml.strip():
        raise ArxivError("arXiv returned an empty response.")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise ArxivError(f"arXiv returned malformed Atom XML: {error}") from error
    atom = "{http://www.w3.org/2005/Atom}"
    candidates: list[ArxivCandidate] = []
    for entry in root.findall(f"{atom}entry"):
        raw_id = _xml_text(entry, f"{atom}id")
        title = _xml_text(entry, f"{atom}title")
        if not raw_id or not title:
            continue
        abstract_url = raw_id.replace("http://", "https://", 1)
        arxiv_id = abstract_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
        authors = tuple(
            author_name
            for author in entry.findall(f"{atom}author")
            if (author_name := _xml_text(author, f"{atom}name"))
        )
        categories = tuple(
            category
            for category_node in entry.findall(f"{atom}category")
            if (category := str(category_node.get("term") or "").strip())
        )
        candidates.append(
            ArxivCandidate(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract_url=abstract_url,
                summary=_xml_text(entry, f"{atom}summary") or "",
                published=_xml_text(entry, f"{atom}published"),
                updated=_xml_text(entry, f"{atom}updated"),
                categories=categories,
            )
        )
    return tuple(candidates)


def _xml_text(node: ElementTree.Element, path: str) -> str | None:
    child = node.find(path)
    if child is None or child.text is None:
        return None
    normalized = " ".join(child.text.split())
    return normalized or None


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
