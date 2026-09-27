from pathlib import Path

from axioms.api import (
    AssessmentBlueprintIn,
    LecturePlanIn,
    ResearchBriefIn,
    WritingDraftIn,
    create_assessment_blueprint,
    create_assessment_instructor_docx,
    create_assessment_student_docx,
    create_lecture_plan,
    create_lecture_plan_docx,
    create_research_bibtex,
    create_research_brief,
    create_research_brief_docx,
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


def research_payload() -> ResearchBriefIn:
    return ResearchBriefIn(
        research_question="How can fuzzy similarity measures support drug-drug interaction prediction?",
        scope="Compare methods and limitations.",
        sources=[
            {
                "source_id": "S01",
                "title": "A verified source record",
                "authors": ["Javed"],
                "year": 2026,
                "publication_kind": "journal_article",
                "doi": "10.1000/example.doi",
                "peer_reviewed": True,
                "supported_claim": "A source-linked claim.",
                "verification_status": "claim_verified",
                "verification_evidence": "Author checked the record and claim.",
            }
        ],
    )


def test_research_brief_handler_exposes_verification_state() -> None:
    body = create_research_brief(research_payload())
    assert body["source_audit"][0]["synthesis_eligible"]


def test_research_export_handlers_return_docx_and_bibtex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    docx_response = create_research_brief_docx(research_payload())
    assert Path(docx_response.path).read_bytes()[:2] == b"PK"
    bibtex_response = create_research_bibtex(research_payload())
    assert "10.1000/example.doi" in bibtex_response.body.decode()


def assessment_payload() -> AssessmentBlueprintIn:
    return AssessmentBlueprintIn(
        topic="Spectral Graph Theory",
        course_level="Graduate",
        assessment_type="quiz",
        duration_minutes=30,
        total_marks=20,
        question_count=2,
        learning_outcomes=[
            {"outcome_id": "LO1", "text": "Explain graph matrices.", "bloom_level": "understand"},
            {"outcome_id": "LO2", "text": "Apply a spectral method.", "bloom_level": "apply"},
        ],
        approved_source_scope="Instructor-approved graph theory lecture notes.",
    )


def test_assessment_handler_has_exact_mark_allocation() -> None:
    body = create_assessment_blueprint(assessment_payload())
    assert sum(item["marks"] for item in body["questions"]) == 20


def test_assessment_export_handlers_separate_student_and_instructor_docs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    student = create_assessment_student_docx(assessment_payload())
    instructor = create_assessment_instructor_docx(assessment_payload())
    assert Path(student.path).read_bytes()[:2] == b"PK"
    assert Path(instructor.path).read_bytes()[:2] == b"PK"
