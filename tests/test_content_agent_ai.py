from axioms.content_agent import ContentFormat, ContentRequest, LanguageMode
from axioms.content_agent_ai import ContentStepKind, run_agentic_content_review
from axioms.llm import DisabledProvider, FakeProvider, LLMMessage


def _request() -> ContentRequest:
    return ContentRequest(
        topic="Spectral Graph Theory",
        format=ContentFormat.YOUTUBE_VIDEO,
        audience="Graduate mathematics students",
        duration_minutes=15,
        approved_source_scope="Instructor-approved lecture notes on spectral graph theory.",
        learning_outcomes=("Explain intuition.", "Interpret a worked example."),
        language_mode=LanguageMode.BILINGUAL,
        application_context="PageRank",
    )


def test_agentic_content_generates_internal_review_and_auditable_trace() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages) -> str:
        captured["messages"] = list(messages)
        return (
            "Explain intuition. and Interpret a worked example. are covered. "
            "Editor checklist: verify source-bound claims and accessibility before approval."
        )

    result = run_agentic_content_review(_request(), provider=FakeProvider(responder))
    assert result.generation_enabled
    assert result.editorial_review is not None
    assert result.editorial_approval_required
    assert result.publication_blocked
    assert [step.kind for step in result.agent_trace] == [
        ContentStepKind.PLAN,
        ContentStepKind.SYNTHESIS,
        ContentStepKind.GUARDRAIL,
    ]
    assert result.autoeval is not None
    assert result.autoeval["missing_required_elements"] == []
    prompt = " ".join(message.content for message in captured["messages"])
    assert "not a student-facing script" in prompt
    assert "Explain intuition." in prompt


def test_agentic_content_degrades_to_deterministic_package_when_llm_is_disabled() -> None:
    result = run_agentic_content_review(_request(), provider=DisabledProvider())
    assert not result.generation_enabled
    assert result.editorial_review is None
    assert result.autoeval is None
    assert result.package.allocated_minutes == 15
    assert result.agent_trace[-1].kind is ContentStepKind.NOTE
