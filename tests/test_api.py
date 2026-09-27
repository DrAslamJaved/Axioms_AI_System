from pathlib import Path

from axioms.api import LecturePlanIn, create_lecture_plan, create_lecture_plan_docx


def lecture_payload() -> LecturePlanIn:
    return LecturePlanIn(
        topic="Spectral Graph Theory",
        course_level="Graduate",
        duration_minutes=75,
        audience="MS Mathematics, Year 1",
        learning_outcomes=[
            "Explain the intuition behind spectral graph methods.",
            "Apply graph matrices to a small example.",
        ],
        include_computational_activity=True,
    )


def test_lecture_plan_handler_returns_duration_accurate_plan() -> None:
    body = create_lecture_plan(lecture_payload())
    assert sum(section["minutes"] for section in body["sections"]) == 75
    assert body["request"]["topic"] == "Spectral Graph Theory"


def test_lecture_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_lecture_plan_docx(lecture_payload())
    assert response.media_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = Path(response.path)
    assert document.exists()
    assert document.read_bytes()[:2] == b"PK"
