import pytest

from axioms.tools import (
    ArxivClient,
    ArxivError,
    CrossrefClient,
    CrossrefError,
    TavilyClient,
    TavilyError,
    title_similarity,
    titles_match,
)

ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2601.01234v1</id>
    <updated>2026-01-10T12:00:00Z</updated>
    <published>2026-01-09T12:00:00Z</published>
    <title> Fuzzy Similarity for DTI Prediction </title>
    <summary> A preprint candidate summary. </summary>
    <author><name>A. Javed</name></author>
    <category term="cs.LG" />
  </entry>
</feed>"""


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


def test_arxiv_discovery_returns_unverified_preprint_candidates_and_caches_result() -> None:
    captured: dict[str, object] = {}

    def fetch(url: str) -> str:
        captured["url"] = url
        return ARXIV_FEED

    client = ArxivClient(fetch=fetch, clock=lambda: 100.0)
    first = client.discover("fuzzy similarity DTI prediction")
    second = client.discover("fuzzy similarity DTI prediction")
    assert "export.arxiv.org/api/query" in str(captured["url"])
    assert "max_results=5" in str(captured["url"])
    assert first.candidates[0].arxiv_id == "2601.01234v1"
    assert first.candidates[0].abstract_url == "https://arxiv.org/abs/2601.01234v1"
    assert first.candidates[0].categories == ("cs.LG",)
    assert not first.cached
    assert second.cached
    assert "preprint candidates" in first.verification_boundary


def test_arxiv_discovery_rate_limits_distinct_live_queries_and_rejects_bad_xml() -> None:
    now = [100.0]
    client = ArxivClient(fetch=lambda url: ARXIV_FEED, clock=lambda: now[0])
    client.discover("fuzzy similarity DTI prediction")
    with pytest.raises(ArxivError, match="rate limited"):
        client.discover("spectral graph theory literature")
    bad_xml_client = ArxivClient(fetch=lambda url: "not xml", clock=lambda: 100.0)
    with pytest.raises(ArxivError, match="malformed"):
        bad_xml_client.discover("fuzzy similarity DTI prediction")
