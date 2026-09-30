"""Tests for the agentic research vertical.

All offline and deterministic: Crossref is a fake ``fetch`` and the LLM is a
:class:`FakeProvider`, so the whole agent loop -- tool use, state transitions,
bounded synthesis, guardrail -- is exercised without network or API keys.
"""

from axioms.llm import DisabledProvider, FakeProvider, LLMMessage
from axioms.research_agent import (
    EvidenceSource,
    PublicationKind,
    ResearchRequest,
    VerificationStatus,
)
from axioms.research_agent_ai import StepKind, run_agentic_research_brief
from axioms.tools import CrossrefClient


def _crossref_message(title: str, work_type: str = "journal-article", year: int = 2026) -> dict:
    return {
        "message": {
            "title": [title],
            "type": work_type,
            "author": [{"given": "A.", "family": "Javed"}],
            "published-print": {"date-parts": [[year, 1, 1]]},
        }
    }


def _fetch_for(mapping: dict[str, dict]):
    def fetch(url: str) -> dict:
        for fragment, message in mapping.items():
            if fragment in url:
                return message
        raise AssertionError(f"unexpected DOI lookup: {url}")

    return fetch


def _claim_verified_s01() -> EvidenceSource:
    return EvidenceSource(
        source_id="S01",
        title="Fuzzy similarity for DDI prediction",
        authors=("Javed",),
        year=2026,
        publication_kind=PublicationKind.JOURNAL_ARTICLE,
        doi="10.1000/s01",
        url=None,
        peer_reviewed=True,
        supported_claim="Cardinality-based fuzzy similarity improves DDI ranking.",
        verification_status=VerificationStatus.CLAIM_VERIFIED,
        verification_evidence="Author verified the claim against the source.",
    )


def _unverified_preprint_s02() -> EvidenceSource:
    return EvidenceSource(
        source_id="S02",
        title="A preprint on graph embeddings",
        authors=("Author",),
        year=2025,
        publication_kind=PublicationKind.PREPRINT,
        doi="10.1000/s02",
        url=None,
        peer_reviewed=False,
        supported_claim="Graph embeddings help link prediction, not yet verified.",
        verification_status=VerificationStatus.UNVERIFIED,
        verification_evidence=None,
    )


def _request(*sources: EvidenceSource) -> ResearchRequest:
    return ResearchRequest(
        research_question="How do fuzzy similarity measures support DDI prediction?",
        scope="Methods and limitations.",
        sources=tuple(sources),
    )


def test_agent_verifies_metadata_and_synthesises_only_verified_claims() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages):
        captured["messages"] = list(messages)
        return "Fuzzy similarity improves DDI ranking [S01]. Limitations: single study."

    fetch = _fetch_for(
        {
            "s01": _crossref_message("Fuzzy similarity for DDI prediction"),
            "s02": _crossref_message("A preprint on graph embeddings", work_type="posted-content"),
        }
    )
    result = run_agentic_research_brief(
        _request(_claim_verified_s01(), _unverified_preprint_s02()),
        provider=FakeProvider(responder),
        crossref=CrossrefClient(fetch=fetch),
    )

    assert result.synthesis_enabled
    assert "[S01]" in result.synthesis

    kinds = [step.kind for step in result.agent_trace]
    assert kinds.count(StepKind.TOOL_CALL) == 2
    assert StepKind.SYNTHESIS in kinds
    assert any(step.kind is StepKind.STATE_TRANSITION and "S02" in step.summary for step in result.agent_trace)

    prompt_text = " ".join(message.content for message in captured["messages"])
    assert "Cardinality-based fuzzy similarity improves DDI ranking." in prompt_text
    assert "Graph embeddings help link prediction" not in prompt_text

    assert result.autoeval is not None
    assert result.autoeval["quality_signal_percent"] == 100
    assert result.autoeval["missing_required_elements"] == []
    assert result.brief.verified_claims == (
        "[S01] Cardinality-based fuzzy similarity improves DDI ranking.",
    )


def test_agent_degrades_gracefully_without_an_llm() -> None:
    fetch = _fetch_for({"s01": _crossref_message("Fuzzy similarity for DDI prediction")})
    result = run_agentic_research_brief(
        _request(_claim_verified_s01()),
        provider=DisabledProvider(),
        crossref=CrossrefClient(fetch=fetch),
    )
    assert not result.synthesis_enabled
    assert result.synthesis is None
    assert result.autoeval is None
    assert result.brief.verified_claims  # the deterministic brief is intact
    assert any("LLM disabled" in step.summary for step in result.agent_trace)


def test_agent_flags_title_mismatch_and_does_not_verify() -> None:
    mismatch = EvidenceSource(
        source_id="S03",
        title="A correct sounding title",
        authors=("Author",),
        year=2024,
        publication_kind=PublicationKind.JOURNAL_ARTICLE,
        doi="10.1000/s03",
        url=None,
        peer_reviewed=False,
        supported_claim=None,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_evidence=None,
    )
    fetch = _fetch_for({"s03": _crossref_message("An utterly unrelated paper")})
    result = run_agentic_research_brief(
        _request(mismatch), provider=DisabledProvider(), crossref=CrossrefClient(fetch=fetch)
    )
    assert any("S03" in note for note in result.discrepancies)
    audit = {row["source_id"]: row for row in result.brief.to_dict()["source_audit"]}
    assert not audit["S03"]["synthesis_eligible"]


def test_agent_flags_preprint_marked_as_peer_reviewed() -> None:
    mislabelled = EvidenceSource(
        source_id="S04",
        title="A journal-titled work",
        authors=("Author",),
        year=2024,
        publication_kind=PublicationKind.JOURNAL_ARTICLE,
        doi="10.1000/s04",
        url=None,
        peer_reviewed=True,
        supported_claim=None,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_evidence=None,
    )
    fetch = _fetch_for({"s04": _crossref_message("A journal-titled work", work_type="posted-content")})
    result = run_agentic_research_brief(
        _request(mislabelled), provider=DisabledProvider(), crossref=CrossrefClient(fetch=fetch)
    )
    assert any("preprint" in note.casefold() for note in result.discrepancies)


def test_agent_survives_crossref_outage() -> None:
    source = EvidenceSource(
        source_id="S05",
        title="Some work",
        authors=("Author",),
        year=2024,
        publication_kind=PublicationKind.JOURNAL_ARTICLE,
        doi="10.1000/s05",
        url=None,
        peer_reviewed=False,
        supported_claim=None,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_evidence=None,
    )

    def boom(url: str) -> dict:
        raise ConnectionError("network down")

    result = run_agentic_research_brief(
        _request(source), provider=DisabledProvider(), crossref=CrossrefClient(fetch=boom)
    )
    assert any("Crossref unavailable" in step.summary for step in result.agent_trace)
    audit = {row["source_id"]: row for row in result.brief.to_dict()["source_audit"]}
    assert not audit["S05"]["synthesis_eligible"]


def test_agent_notes_sources_without_a_doi() -> None:
    no_doi = EvidenceSource(
        source_id="S06",
        title="A work with only a URL",
        authors=("Author",),
        year=2024,
        publication_kind=PublicationKind.OTHER,
        doi=None,
        url="https://example.org/work",
        peer_reviewed=False,
        supported_claim=None,
        verification_status=VerificationStatus.UNVERIFIED,
        verification_evidence=None,
    )
    result = run_agentic_research_brief(
        _request(no_doi), provider=DisabledProvider(), crossref=CrossrefClient(fetch=lambda url: {})
    )
    assert any("no DOI" in step.summary for step in result.agent_trace)
