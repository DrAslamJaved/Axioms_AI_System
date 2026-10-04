from dataclasses import replace
from pathlib import Path

import pytest
from docx import Document

from axioms.llm import DisabledProvider, FakeProvider, LLMMessage
from axioms.social_media_agent import (
    RecentSocialPost,
    SocialMediaRequest,
    SocialObjective,
    SocialPlatform,
    build_social_media_package,
    export_docx,
)


def request() -> SocialMediaRequest:
    return SocialMediaRequest(
        topic="Spectral Graph Theory",
        audience="Graduate mathematics students",
        platforms=(SocialPlatform.LINKEDIN, SocialPlatform.INSTAGRAM, SocialPlatform.X),
        objective=SocialObjective.EDUCATE,
        approved_source_scope="Instructor-approved spectral graph theory lecture notes.",
        verified_facts=("The draft is based on instructor-approved lecture notes.",),
        call_to_action="Invite questions after reviewing the course notes.",
    )


def test_social_package_is_platform_native_and_blocked_from_external_action() -> None:
    package = build_social_media_package(request())
    assert [item.format for item in package.platform_drafts] == [
        "professional post",
        "five-slide carousel",
        "five-post thread",
    ]
    assert package.approval_required
    assert package.external_action_blocked
    assert all("not scheduled" in item.status for item in package.proposed_calendar)



def test_disabled_llm_retains_the_deterministic_social_package() -> None:
    baseline = build_social_media_package(request())
    package = build_social_media_package(request(), provider=DisabledProvider())
    assert package == baseline


def test_fake_llm_enriches_internal_asset_briefs_without_changing_public_drafts() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages: list[LLMMessage]) -> str:
        captured["messages"] = messages
        return "---".join(
            f"Internal visual-planning guidance for platform {number}; verify permissions and accessibility before approval."
            for number in range(1, 4)
        )

    baseline = build_social_media_package(request(), provider=DisabledProvider())
    package = build_social_media_package(request(), provider=FakeProvider(responder))

    assert [draft.platform for draft in package.platform_drafts] == [
        draft.platform for draft in baseline.platform_drafts
    ]
    assert [draft.format for draft in package.platform_drafts] == [
        draft.format for draft in baseline.platform_drafts
    ]
    assert [draft.headline for draft in package.platform_drafts] == [
        draft.headline for draft in baseline.platform_drafts
    ]
    assert [draft.draft_copy for draft in package.platform_drafts] == [
        draft.draft_copy for draft in baseline.platform_drafts
    ]
    assert package.proposed_calendar == baseline.proposed_calendar
    assert package.publication_checks == baseline.publication_checks
    assert package.external_action_blocked
    assert package.topic_cooldown_hours == 48
    assert package.platform_drafts[0].asset_brief.startswith("Internal visual-planning guidance")
    prompt = " ".join(message.content for message in captured["messages"])
    assert "Instructor-approved spectral graph theory lecture notes" in prompt
    assert "write or revise post copy" in prompt
    assert "48-hour cooldown" in prompt


def test_malformed_or_failed_llm_output_retains_the_deterministic_social_package() -> None:
    baseline = build_social_media_package(request(), provider=DisabledProvider())
    malformed = build_social_media_package(request(), provider=FakeProvider(lambda _messages: "one brief only"))

    class BrokenProvider:
        name = "broken"

        def complete(self, messages, *, max_tokens: int = 1024, temperature: float = 0.2):
            raise RuntimeError("provider unavailable")

    failed = build_social_media_package(request(), provider=BrokenProvider())
    assert malformed == baseline
    assert failed == baseline


def test_same_topic_within_48_hours_is_rejected() -> None:
    blocked = replace(
        request(),
        recent_posts=(
            RecentSocialPost(
                platform=SocialPlatform.LINKEDIN,
                topic="spectral   graph theory",
                hours_since_publication=47,
            ),
        ),
    )
    with pytest.raises(ValueError, match="48-hour cooldown"):
        build_social_media_package(blocked)


def test_social_docx_contains_topic(tmp_path: Path) -> None:
    destination = export_docx(build_social_media_package(request()), tmp_path / "social_media.docx")
    document = Document(destination)
    assert destination.exists()
    assert "Spectral Graph Theory" in document.paragraphs[0].text
