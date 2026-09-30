import pytest

from axioms.tools import (
    CrossrefClient,
    CrossrefError,
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
