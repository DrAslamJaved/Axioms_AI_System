from dataclasses import replace
from pathlib import Path

import pytest
from docx import Document

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
