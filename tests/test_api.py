from pathlib import Path

from axioms.api import (
    LecturePlanIn,
    WritingDraftIn,
    create_lecture_plan,
    create_lecture_plan_docx,
    create_writing_draft,
    create_writing_draft_docx,
)


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


def writing_payload() -> WritingDraftIn:
    return WritingDraftIn(
        document_type="email",
        subject="Research collaboration update",
        audience="Academic collaborator",
        purpose="Provide a concise update and agree the next step.",
        key_points=["State current progress."],
        verified_facts=["The author reviewed the stated project progress."],
    )


def test_writing_draft_handler_returns_review_first_draft() -> None:
    body = create_writing_draft(writing_payload())
    assert body["approval_required"]
    assert body["subject_line"] == "Regarding: Research collaboration update"


def test_writing_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_writing_draft_docx(writing_payload())
    document = Path(response.path)
    assert document.exists()
    assert document.read_bytes()[:2] == b"PK"
