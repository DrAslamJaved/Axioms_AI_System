from pathlib import Path

from docx import Document

from axioms.autoeval_agent import (
    AutoEvalRequest,
    CheckStatus,
    EvaluatedAgent,
    evaluate_deliverable,
    export_docx,
)


def request() -> AutoEvalRequest:
    return AutoEvalRequest(
        evaluated_agent=EvaluatedAgent.LECTURE,
        deliverable_title="Spectral Graph Theory lecture plan",
        artifact_text="The plan includes intuition, a formal definition, worked example, and [S01].",
        required_elements=("intuition", "formal definition", "worked example"),
        evidence_markers=("[S01]",),
        public_facing=True,
    )


def test_autoeval_records_deterministic_contract_checks_without_approval() -> None:
    report = evaluate_deliverable(request())
    assert report.quality_signal_percent == 75
    assert report.human_review_required
    assert report.automatic_reconfiguration_blocked
    assert report.external_action_blocked
    assert report.checks[-1].status is CheckStatus.REVIEW


def test_autoeval_identifies_missing_required_marker_and_sensitive_data_block() -> None:
    report = evaluate_deliverable(
        AutoEvalRequest(
            evaluated_agent=EvaluatedAgent.WRITING,
            deliverable_title="Draft",
            artifact_text="A concise introduction.",
            required_elements=("introduction", "conclusion"),
            declared_sensitive_data=True,
        )
    )
    assert report.missing_required_elements == ("conclusion",)
    assert any(item.status is CheckStatus.BLOCK for item in report.checks)


def test_autoeval_hash_is_repeatable_and_docx_contains_title(tmp_path: Path) -> None:
    first = evaluate_deliverable(request())
    second = evaluate_deliverable(request())
    destination = export_docx(first, tmp_path / "autoeval_report.docx")
    document = Document(destination)
    assert first.artifact_sha256 == second.artifact_sha256
    assert "Spectral Graph Theory" in document.paragraphs[0].text
