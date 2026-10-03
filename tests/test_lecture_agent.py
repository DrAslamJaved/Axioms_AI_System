from pathlib import Path

import pytest
from docx import Document

from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx
from axioms.llm import DisabledProvider, FakeProvider


def request() -> LectureRequest:
    return LectureRequest(
        topic="Spectral Graph Theory",
        course_level="Graduate",
        duration_minutes=75,
        audience="MS Mathematics, Year 1",
        prior_knowledge="Linear algebra and basic graph theory",
        learning_outcomes=(
            "Explain the intuition behind spectral graph methods.",
            "Apply graph matrices to a small example.",
            "Interpret a real-world use case.",
        ),
        application_context="PageRank and network clustering",
        include_computational_activity=True,
    )


def test_plan_uses_entire_requested_duration() -> None:
    plan = build_lecture_plan(request())
    assert plan.total_minutes == 75
    assert [section.title for section in plan.sections] == [
        "Opening hook",
        "Intuition and prior knowledge",
        "Formal development",
        "Worked example",
        "Guided application",
        "Retrieval and exit check",
    ]


def test_plan_includes_teaching_style_and_review_controls() -> None:
    plan = build_lecture_plan(request())
    assert "Python/NumPy" in plan.practice_activity
    assert "Verify every theorem statement" in plan.review_checklist[0]
    assert "Formal development" in plan.to_markdown()


def test_disabled_llm_retains_the_deterministic_review_first_plan() -> None:
    plan = build_lecture_plan(request(), provider=DisabledProvider())

    assert plan.sections[0].purpose == "Activate curiosity through a familiar problem."
    assert plan.sections[0].instructor_prompt == "Where might Spectral Graph Theory arise outside the textbook?"
    assert plan.total_minutes == 75


def test_fake_llm_enriches_section_wording_without_changing_the_timing_contract() -> None:
    response = "\n---\n".join(
        f"Purpose: Custom purpose {index}.\nInstructor prompt: Custom instructor prompt {index}."
        for index in range(1, 7)
    )
    captured_messages = []
    provider = FakeProvider(lambda messages: (captured_messages.extend(messages), response)[1])

    plan = build_lecture_plan(request(), provider=provider)

    assert plan.total_minutes == 75
    assert [section.title for section in plan.sections] == [
        "Opening hook",
        "Intuition and prior knowledge",
        "Formal development",
        "Worked example",
        "Guided application",
        "Retrieval and exit check",
    ]
    assert plan.sections[0].purpose == "Custom purpose 1."
    assert plan.sections[-1].instructor_prompt == "Custom instructor prompt 6."
    assert "Spectral Graph Theory" in captured_messages[1].content
    assert "Learning outcomes:" in captured_messages[1].content


def test_malformed_llm_output_falls_back_without_changing_the_plan() -> None:
    plan = build_lecture_plan(request(), provider=FakeProvider(lambda _messages: "unstructured response"))

    assert plan.sections[0].purpose == "Activate curiosity through a familiar problem."
    assert plan.sections[-1].title == "Retrieval and exit check"


def test_provider_failure_falls_back_without_changing_the_plan() -> None:
    def fail(_messages) -> str:
        raise RuntimeError("provider unavailable")

    plan = build_lecture_plan(request(), provider=FakeProvider(fail))

    assert plan.sections[0].purpose == "Activate curiosity through a familiar problem."
    assert plan.total_minutes == 75


def test_invalid_duration_is_rejected() -> None:
    invalid = LectureRequest(
        topic="Graph theory",
        course_level="Undergraduate",
        duration_minutes=20,
        audience="BS Mathematics",
        learning_outcomes=("Explain the topic.", "Apply the topic."),
    )
    with pytest.raises(ValueError, match="between 30 and 240"):
        build_lecture_plan(invalid)


def test_docx_export_contains_the_topic(tmp_path: Path) -> None:
    destination = export_docx(build_lecture_plan(request()), tmp_path / "lecture_plan.docx")
    document = Document(destination)
    assert destination.exists()
    assert "Spectral Graph Theory" in document.paragraphs[0].text

