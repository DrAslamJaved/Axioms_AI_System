from pathlib import Path

from docx import Document

from axioms.autoeval_agent import (
    AutoEvalRequest,
    CheckStatus,
    EvaluatedAgent,
    evaluate_deliverable,
    export_docx,
)
from axioms.llm import DisabledProvider, FakeProvider, LLMMessage


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



def test_disabled_llm_retains_deterministic_autoeval_results() -> None:
    baseline = evaluate_deliverable(request())
    report = evaluate_deliverable(request(), provider=DisabledProvider())
    assert report == baseline
    assert report.qualitative_summary is None


def test_fake_llm_adds_non_authoritative_qualitative_summary_only() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages: list[LLMMessage]) -> str:
        captured["messages"] = messages
        return "The deterministic marker checks require human review before any decision or external action."

    baseline = evaluate_deliverable(request())
    report = evaluate_deliverable(request(), provider=FakeProvider(responder))
    assert report.artifact_sha256 == baseline.artifact_sha256
    assert report.checks == baseline.checks
    assert report.required_elements_found == baseline.required_elements_found
    assert report.missing_required_elements == baseline.missing_required_elements
    assert report.quality_signal_percent == baseline.quality_signal_percent
    assert report.review_boundary == baseline.review_boundary
    assert report.human_review_required
    assert report.automatic_reconfiguration_blocked
    assert report.external_action_blocked
    assert report.qualitative_summary is not None
    prompt = " ".join(message.content for message in captured["messages"])
    assert "Artifact SHA-256" in prompt
    assert "The plan includes" not in prompt
    assert "deterministic SHA-256" in prompt


def test_malformed_or_failed_llm_summary_is_omitted_without_changing_checks() -> None:
    baseline = evaluate_deliverable(request())
    malformed = evaluate_deliverable(request(), provider=FakeProvider(lambda _messages: "- list output"))

    class BrokenProvider:
        name = "broken"

        def complete(self, messages, *, max_tokens: int = 1024, temperature: float = 0.2):
            raise RuntimeError("provider unavailable")

    failed = evaluate_deliverable(request(), provider=BrokenProvider())
    assert malformed == baseline
    assert failed == baseline


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
