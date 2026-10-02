import pytest

from axioms.tools import (
    CrossrefClient,
    CrossrefError,
    TavilyClient,
    TavilyError,
    title_similarity,
    titles_match,
)


def _message(title: str, work_type: str = "journal-article", year: int = 2026) -> dict:
    return {
        "message": {
            "title": [title],
            "type": work_type,
            "author": [{"given": "A.", "family": "Javed"}, {"given": "B.", "family": "Researcher"}],
            "published-print": {"date-parts": [[year, 3, 1]]},
        }
    }


def test_lookup_parses_a_crossref_record() -> None:
    client = CrossrefClient(fetch=lambda url: _message("Spectral Graph Theory"))
    record = client.lookup("10.1000/example.doi")
    assert record.title == "Spectral Graph Theory"
    assert record.authors[0] == "A. Javed"
    assert record.year == 2026
    assert not record.is_preprint


def test_lookup_detects_preprints() -> None:
    client = CrossrefClient(fetch=lambda url: _message("A preprint", work_type="posted-content"))
    record = client.lookup("10.1000/preprint.doi")
    assert record.is_preprint


def test_lookup_normalises_doi_url_prefix() -> None:
    captured: dict[str, str] = {}

    def fetch(url: str) -> dict:
        captured["url"] = url
        return _message("Anything")

    CrossrefClient(fetch=fetch).lookup("https://doi.org/10.1000/example.doi")
    assert captured["url"].endswith("10.1000%2Fexample.doi")


def test_lookup_rejects_empty_doi() -> None:
    with pytest.raises(CrossrefError):
        CrossrefClient(fetch=lambda url: {}).lookup("   ")


def test_lookup_surfaces_missing_message_as_error() -> None:
    with pytest.raises(CrossrefError):
        CrossrefClient(fetch=lambda url: {"status": "ok"}).lookup("10.1/x")


def test_network_failure_is_wrapped_as_crossref_error() -> None:
    def boom(url: str) -> dict:
        raise TimeoutError("network down")

    with pytest.raises(CrossrefError):
        CrossrefClient(fetch=boom).lookup("10.1/x")


def test_title_similarity_is_punctuation_and_case_insensitive() -> None:
    assert title_similarity("Graph Spectra!", "graph spectra") == 1.0
    assert titles_match("Fuzzy similarity measures for DDI", "Fuzzy Similarity Measures for DDI")
    assert not titles_match("Totally different", "Nothing alike at all")


def test_tavily_discovery_returns_only_https_candidate_sources() -> None:
    captured: dict[str, object] = {}

    def fetch(url: str, payload: dict) -> dict:
        captured["url"] = url
        captured["payload"] = payload
        return {
            "results": [
                {
                    "title": "Fuzzy similarity for DTI prediction",
                    "url": "https://example.org/paper",
                    "content": "A candidate source summary.",
                    "score": 0.91,
                    "published_date": "2026-01-10",
                },
                {"title": "Discarded insecure result", "url": "http://example.org/insecure"},
            ]
        }

    result = TavilyClient("test-key", fetch=fetch).discover("fuzzy similarity DTI prediction")
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["payload"] == {
        "api_key": "test-key",
        "query": "fuzzy similarity DTI prediction",
        "search_depth": "advanced",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
        "topic": "general",
    }
    assert [source.title for source in result.sources] == ["Fuzzy similarity for DTI prediction"]
    assert "unverified candidates" in result.verification_boundary


def test_tavily_discovery_fails_closed_without_a_key() -> None:
    with pytest.raises(TavilyError, match="not configured"):
        TavilyClient(None, fetch=lambda url, payload: {}).discover("fuzzy similarity DTI prediction")


def test_tavily_discovery_rejects_invalid_query_and_response() -> None:
    with pytest.raises(TavilyError, match="at least 8"):
        TavilyClient("test-key", fetch=lambda url, payload: {}).discover("short")
    with pytest.raises(TavilyError, match="no usable"):
        TavilyClient("test-key", fetch=lambda url, payload: {}).discover("fuzzy similarity DTI prediction")
