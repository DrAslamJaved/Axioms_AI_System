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
from urllib.parse import quote
from urllib.request import Request, urlopen

CROSSREF_WORKS_URL = "https://api.crossref.org/works/"

# Crossref work types that are not peer-reviewed publications on their own.
PREPRINT_TYPES = {"posted-content", "preprint"}

# fetch(url) -> parsed JSON object. Injected so the network can be faked in tests.
Fetch = Callable[[str], dict]


class CrossrefError(RuntimeError):
    """Raised when a DOI cannot be resolved or the response is unusable."""


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
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https host
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
