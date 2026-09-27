from pathlib import Path

import pytest
from docx import Document

from axioms.research_agent import (
    EvidenceSource,
    PublicationKind,
    ResearchRequest,
    VerificationStatus,
    build_research_brief,
    export_docx,
)


def verified_source() -> EvidenceSource:
    return EvidenceSource(
        source_id="S01",
        title="A verified source record",
        authors=("Javed", "Researcher"),
        year=2026,
        publication_kind=PublicationKind.JOURNAL_ARTICLE,
        doi="10.1000/example.doi",
        url=None,
        peer_reviewed=True,
        supported_claim="The verified source supports this narrowly stated claim.",
        verification_status=VerificationStatus.CLAIM_VERIFIED,
        verification_evidence="The author checked the metadata and claim against the source.",
    )


def request() -> ResearchRequest:
    return ResearchRequest(
        research_question="How can fuzzy similarity measures support drug-drug interaction prediction?",
        scope="Compare methods, datasets, metrics, and limitations.",
        sources=(verified_source(),),
    )


def test_claim_verified_source_is_the_only_synthesis_eligible_source() -> None:
    brief = build_research_brief(request())
    assert brief.source_audit[0].synthesis_eligible
    assert brief.verified_claims == ("[S01] The verified source supports this narrowly stated claim.",)
    assert "10.1000/example.doi" in brief.verified_bibtex()


def test_unverified_source_is_queued_and_blocked() -> None:
    source = EvidenceSource(
        source_id="S02",
        title="Unverified source record",
        authors=("Author",),
        year=2025,
        publication_kind=PublicationKind.PREPRINT,
        doi="10.1000/unverified.doi",
        url=None,
        peer_reviewed=False,
        supported_claim="A claim that is not yet verified.",
        verification_status=VerificationStatus.UNVERIFIED,
    )
    brief = build_research_brief(
        ResearchRequest(research_question="Question", scope="Scope", sources=(source,))
    )
    assert not brief.source_audit[0].synthesis_eligible
    assert len(brief.verification_queue) == 2
    assert brief.verified_bibtex() == ""


def test_preprint_cannot_be_marked_peer_reviewed() -> None:
    invalid = EvidenceSource(
        source_id="S03",
        title="Invalid status record",
        authors=("Author",),
        year=2025,
        publication_kind=PublicationKind.PREPRINT,
        doi="10.1000/preprint.doi",
        url=None,
        peer_reviewed=True,
        supported_claim=None,
        verification_status=VerificationStatus.UNVERIFIED,
    )
    with pytest.raises(ValueError, match="preprint"):
        build_research_brief(ResearchRequest(research_question="Question", scope="Scope", sources=(invalid,)))


def test_docx_export_contains_question(tmp_path: Path) -> None:
    destination = export_docx(build_research_brief(request()), tmp_path / "research_brief.docx")
    document = Document(destination)
    assert destination.exists()
    assert "How can fuzzy similarity" in document.paragraphs[2].text
