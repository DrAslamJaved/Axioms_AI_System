from pathlib import Path

import pytest
from docx import Document

from axioms.lecture_agent import LectureRequest, build_lecture_plan, export_docx


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

