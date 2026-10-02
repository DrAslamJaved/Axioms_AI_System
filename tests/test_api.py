from pathlib import Path

from fastapi import BackgroundTasks

from axioms import api
from axioms.api import (
    AssessmentBlueprintIn,
    AutoEvalReportIn,
    ContentPackageIn,
    FeedbackIn,
    LecturePlanIn,
    PortfolioPackageIn,
    PreferenceProposalIn,
    ProposalDecisionIn,
    ResearchBriefIn,
    ResearchDiscoveryIn,
    SocialMediaPackageIn,
    WritingDraftIn,
    create_assessment_blueprint,
    create_assessment_instructor_docx,
    create_assessment_student_docx,
    create_autoeval_report,
    create_autoeval_report_docx,
    create_content_package,
    create_content_package_docx,
    create_lecture_plan,
    create_lecture_plan_docx,
    create_portfolio_package,
    create_portfolio_package_docx,
    create_preference_proposal,
    create_research_bibtex,
    create_research_brief,
    create_research_brief_docx,
    create_social_media_package,
    create_social_media_package_docx,
    create_writing_draft,
    create_writing_draft_docx,
    decide_preference_proposal,
    discover_research_sources,
    list_agents,
    list_personal_kb_entries,
    system_readiness,
)
from axioms.tools import TavilyClient


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
    response = create_lecture_plan_docx(lecture_payload(), BackgroundTasks())
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
    response = create_writing_draft_docx(writing_payload(), BackgroundTasks())
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


def test_research_discovery_handler_returns_unverified_candidates(monkeypatch) -> None:
    def fetch(url: str, payload: dict) -> dict:
        assert payload["query"] == "fuzzy similarity DTI literature"
        return {
            "results": [
                {
                    "title": "Candidate source",
                    "url": "https://example.org/candidate",
                    "content": "Search excerpt",
                }
            ]
        }

    monkeypatch.setattr(api, "_tavily_client", lambda: TavilyClient("test-key", fetch=fetch))
    body = discover_research_sources(ResearchDiscoveryIn(query="fuzzy similarity DTI literature"))
    assert body["sources"][0]["title"] == "Candidate source"
    assert "unverified candidates" in body["verification_boundary"]


def test_research_export_handlers_return_docx_and_bibtex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    docx_response = create_research_brief_docx(research_payload(), BackgroundTasks())
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
    student = create_assessment_student_docx(assessment_payload(), BackgroundTasks())
    instructor = create_assessment_instructor_docx(assessment_payload(), BackgroundTasks())
    assert Path(student.path).read_bytes()[:2] == b"PK"
    assert Path(instructor.path).read_bytes()[:2] == b"PK"


def content_payload() -> ContentPackageIn:
    return ContentPackageIn(
        topic="Spectral Graph Theory",
        format="youtube_video",
        audience="Graduate mathematics students",
        duration_minutes=15,
        approved_source_scope="Instructor-approved spectral graph theory notes.",
        learning_outcomes=["Explain intuition.", "Interpret a worked example."],
        language_mode="bilingual",
    )


def test_content_handler_returns_a_review_first_package() -> None:
    body = create_content_package(content_payload())
    assert body["publication_approval_required"]
    assert sum(item["minutes"] for item in body["segments"]) == 15


def test_content_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_content_package_docx(content_payload(), BackgroundTasks())
    assert Path(response.path).read_bytes()[:2] == b"PK"


def social_media_payload() -> SocialMediaPackageIn:
    return SocialMediaPackageIn(
        topic="Spectral Graph Theory",
        audience="Graduate mathematics students",
        platforms=["linkedin", "instagram"],
        objective="educate",
        approved_source_scope="Instructor-approved spectral graph theory notes.",
        verified_facts=["The draft is based on instructor-approved lecture notes."],
    )


def test_social_media_handler_returns_drafts_without_external_action() -> None:
    body = create_social_media_package(social_media_payload())
    assert body["approval_required"]
    assert body["external_action_blocked"]
    assert len(body["platform_drafts"]) == 2


def test_social_media_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_social_media_package_docx(social_media_payload(), BackgroundTasks())
    assert Path(response.path).read_bytes()[:2] == b"PK"


def portfolio_payload() -> PortfolioPackageIn:
    return PortfolioPackageIn(
        project_title="Agentic Spectral Graph Theory Learning Toolkit",
        research_summary="A reproducible educational project for spectral graph theory.",
        target_audience="academic_and_industry",
        repository_visibility="public",
        verified_evidence=[
            {
                "evidence_id": "E01",
                "claim": "The project is based on instructor-approved lecture notes.",
                "source_reference": "Internal course-material review record",
                "verified": True,
            }
        ],
    )


def test_portfolio_handler_returns_review_only_package() -> None:
    body = create_portfolio_package(portfolio_payload())
    assert body["approval_required"]
    assert body["github_action_blocked"]


def test_portfolio_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_portfolio_package_docx(portfolio_payload(), BackgroundTasks())
    assert Path(response.path).read_bytes()[:2] == b"PK"


def autoeval_payload() -> AutoEvalReportIn:
    return AutoEvalReportIn(
        evaluated_agent="lecture_design",
        deliverable_title="Spectral Graph Theory lecture plan",
        artifact_text="The plan includes intuition, a formal definition, and a worked example.",
        required_elements=["intuition", "formal definition", "worked example"],
    )


def test_autoeval_handler_returns_review_signal_without_release_approval() -> None:
    body = create_autoeval_report(autoeval_payload())
    assert body["human_review_required"]
    assert body["automatic_reconfiguration_blocked"]


def test_autoeval_docx_handler_returns_a_word_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = create_autoeval_report_docx(autoeval_payload(), BackgroundTasks())
    assert Path(response.path).read_bytes()[:2] == b"PK"


def test_system_integration_handlers_expose_profiles_and_deferrals() -> None:
    agents = list_agents()
    readiness = system_readiness()
    assert len(agents) == 8
    assert readiness["specialist_agent_count"] == 8
    assert not readiness["external_actions_enabled"]


def test_personal_kb_handler_requires_a_recorded_approval() -> None:
    pending = create_preference_proposal(
        PreferenceProposalIn(
            category="teaching_style",
            preference_key="example_sequence",
            preference_value="Start with intuition.",
            rationale="Owner preference for teaching materials.",
        )
    )
    assert pending["decision"] is None
    decided = decide_preference_proposal(
        pending["proposal_id"], ProposalDecisionIn(decision="approve", note="Reviewed")
    )
    assert decided["decision"] == "approve"
    assert any(item["preference_key"] == "example_sequence" for item in list_personal_kb_entries())


def test_feedback_handler_records_explicit_feedback_only() -> None:
    from axioms.api import record_feedback

    feedback = record_feedback(
        FeedbackIn(agent="lecture_design", artifact_reference="lecture_plan_v1", rating=5)
    )
    assert feedback["rating"] == 5
