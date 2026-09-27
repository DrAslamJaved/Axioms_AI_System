from pathlib import Path

import pytest
from docx import Document

from axioms.content_agent import (
    ContentFormat,
    ContentRequest,
    LanguageMode,
    build_content_package,
    export_docx,
)


def request() -> ContentRequest:
    return ContentRequest(
        topic="Spectral Graph Theory",
        format=ContentFormat.YOUTUBE_VIDEO,
        audience="Graduate mathematics students",
        duration_minutes=15,
        approved_source_scope="Instructor-approved lecture notes on spectral graph theory.",
        learning_outcomes=("Explain intuition.", "Interpret a worked example."),
        language_mode=LanguageMode.BILINGUAL,
        application_context="PageRank",
        keywords=("spectral graph theory", "PageRank"),
    )


def test_content_package_uses_entire_requested_duration() -> None:
    package = build_content_package(request())
    assert package.allocated_minutes == 15
    assert len(package.title_options) == 3
    assert package.publication_approval_required


def test_bilingual_package_marks_translation_for_review() -> None:
    package = build_content_package(request())
    assert "Urdu review" in package.segments[-1].speaker_notes
    assert "no numerical performance" in package.thumbnail_brief


def test_invalid_duration_is_rejected() -> None:
    invalid = ContentRequest(
        topic="Topic",
        format=ContentFormat.WORKSHOP,
        audience="Audience",
        duration_minutes=2,
        approved_source_scope="Approved notes.",
        learning_outcomes=("Explain the topic.",),
    )
    with pytest.raises(ValueError, match="between 3 and 240"):
        build_content_package(invalid)


def test_docx_export_contains_topic(tmp_path: Path) -> None:
    destination = export_docx(build_content_package(request()), tmp_path / "content_package.docx")
    document = Document(destination)
    assert destination.exists()
    assert "Spectral Graph Theory" in document.paragraphs[0].text

