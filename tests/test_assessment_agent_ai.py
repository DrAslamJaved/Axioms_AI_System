from axioms.assessment_agent import (
    AssessmentRequest,
    AssessmentType,
    BloomLevel,
    Difficulty,
    LearningOutcome,
)
from axioms.assessment_agent_ai import AssessmentStepKind, run_agentic_assessment_design
from axioms.llm import DisabledProvider, FakeProvider, LLMMessage


def _request() -> AssessmentRequest:
    return AssessmentRequest(
        topic="Spectral Graph Theory",
        course_level="Graduate",
        assessment_type=AssessmentType.QUIZ,
        duration_minutes=30,
        total_marks=20,
        question_count=2,
        learning_outcomes=(
            LearningOutcome("LO1", "Explain the role of graph matrices.", BloomLevel.UNDERSTAND),
            LearningOutcome("LO2", "Apply a spectral method to a small graph.", BloomLevel.APPLY),
        ),
        approved_source_scope="Instructor-approved lecture notes on graph matrices and spectral methods.",
        difficulties=(Difficulty.EASY, Difficulty.MODERATE),
    )


def test_agentic_assessment_generates_instructor_review_and_auditable_trace() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages) -> str:
        captured["messages"] = list(messages)
        return "LO1 and LO2 are aligned. Instructor checklist: verify course values and retain review control."

    result = run_agentic_assessment_design(_request(), provider=FakeProvider(responder))
    assert result.generation_enabled
    assert result.design_review is not None
    assert result.student_release_blocked
    assert [step.kind for step in result.agent_trace] == [
        AssessmentStepKind.PLAN,
        AssessmentStepKind.SYNTHESIS,
        AssessmentStepKind.GUARDRAIL,
    ]
    assert result.autoeval is not None
    assert result.autoeval["missing_required_elements"] == []
    prompt = " ".join(message.content for message in captured["messages"])
    assert "student-facing questions" in prompt
    assert "LO1" in prompt and "LO2" in prompt


def test_agentic_assessment_degrades_to_deterministic_blueprint_when_llm_is_disabled() -> None:
    result = run_agentic_assessment_design(_request(), provider=DisabledProvider())
    assert not result.generation_enabled
    assert result.design_review is None
    assert result.autoeval is None
    assert result.blueprint.allocated_marks == 20
    assert result.agent_trace[-1].kind is AssessmentStepKind.NOTE
