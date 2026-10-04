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
from axioms.llm import DisabledProvider, FakeProvider, LLMMessage


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



def test_disabled_llm_retains_the_deterministic_content_plan() -> None:
    baseline = build_content_package(request())
    package = build_content_package(request(), provider=DisabledProvider())
    assert package == baseline


def test_fake_llm_enriches_internal_speaker_notes_without_changing_plan_controls() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages: list[LLMMessage]) -> str:
        captured["messages"] = messages
        return "---".join(
            (
                f"Internal editorial guidance for content segment {number}; retain the approved scope and review boundary. "
                f"|| اردو: یہ اندرونی منصوبہ بندی کی ہدایت ہے اور منظور شدہ دائرہ کار برقرار رکھتی ہے۔"
            )
            for number in range(1, 6)
        )

    baseline = build_content_package(request(), provider=DisabledProvider())
    package = build_content_package(request(), provider=FakeProvider(responder))

    assert [segment.minutes for segment in package.segments] == [
        segment.minutes for segment in baseline.segments
    ]
    assert [segment.title for segment in package.segments] == [segment.title for segment in baseline.segments]
    assert [segment.purpose for segment in package.segments] == [segment.purpose for segment in baseline.segments]
    assert package.allocated_minutes == baseline.allocated_minutes == 15
    assert package.publication_approval_required
    assert package.segments[0].speaker_notes.startswith("Internal editorial guidance")
    prompt = " ".join(message.content for message in captured["messages"])
    assert "Instructor-approved lecture notes" in prompt
    assert "Explain intuition." in prompt
    assert "not a final script" in prompt
    assert "exact separator ` || اردو: `" in prompt


def test_urdu_synthesis_requires_urdu_script_and_retains_the_plan_controls() -> None:
    urdu_request = ContentRequest(
        topic="Spectral Graph Theory",
        format=ContentFormat.WORKSHOP,
        audience="Graduate mathematics students",
        duration_minutes=15,
        approved_source_scope="Instructor-approved lecture notes on spectral graph theory.",
        learning_outcomes=("Explain intuition.",),
        language_mode=LanguageMode.URDU,
    )
    baseline = build_content_package(urdu_request, provider=DisabledProvider())
    package = build_content_package(
        urdu_request,
        provider=FakeProvider(
            lambda _messages: "---".join(
                "یہ اندرونی منصوبہ بندی کی ہدایت ہے اور منظور شدہ دائرہ کار برقرار رکھتی ہے۔"
                for _ in range(5)
            )
        ),
    )
    assert package.allocated_minutes == baseline.allocated_minutes
    assert all("منظور" in segment.speaker_notes for segment in package.segments)


def test_bilingual_synthesis_without_urdu_script_reverts_to_the_deterministic_plan() -> None:
    baseline = build_content_package(request(), provider=DisabledProvider())
    malformed = build_content_package(
        request(),
        provider=FakeProvider(
            lambda _messages: "---".join(
                "English-only internal editorial guidance for the review boundary." for _ in range(5)
            )
        ),
    )
    assert malformed == baseline


def test_malformed_or_failed_llm_output_retains_the_deterministic_content_plan() -> None:
    baseline = build_content_package(request(), provider=DisabledProvider())
    malformed = build_content_package(request(), provider=FakeProvider(lambda _messages: "one note only"))

    class BrokenProvider:
        name = "broken"

        def complete(self, messages, *, max_tokens: int = 1024, temperature: float = 0.2):
            raise RuntimeError("provider unavailable")

    failed = build_content_package(request(), provider=BrokenProvider())
    assert malformed == baseline
    assert failed == baseline


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


def test_docx_export_contains_topic_and_marks_urdu_notes_right_to_left(tmp_path: Path) -> None:
    package = build_content_package(
        request(),
        provider=FakeProvider(
            lambda _messages: "---".join(
                "Internal editorial guidance retains the approved scope. || اردو: یہ ہدایت منظور شدہ دائرہ کار برقرار رکھتی ہے۔"
                for _ in range(5)
            )
        ),
    )
    destination = export_docx(package, tmp_path / "content_package.docx")
    document = Document(destination)
    assert destination.exists()
    assert "Spectral Graph Theory" in document.paragraphs[0].text
    speaker_note = document.tables[0].rows[1].cells[3].paragraphs[0]
    assert "اردو" in speaker_note.text
    assert "w:bidi" in speaker_note._p.xml
