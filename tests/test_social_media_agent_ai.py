from axioms.llm import DisabledProvider, FakeProvider, LLMMessage
from axioms.social_media_agent import SocialMediaRequest, SocialObjective, SocialPlatform
from axioms.social_media_agent_ai import SocialMediaStepKind, run_agentic_social_media_review


def _request() -> SocialMediaRequest:
    return SocialMediaRequest(
        topic="Spectral Graph Theory",
        audience="Graduate mathematics students",
        platforms=(SocialPlatform.LINKEDIN, SocialPlatform.X),
        objective=SocialObjective.EDUCATE,
        approved_source_scope="Instructor-approved spectral graph theory lecture notes.",
        verified_facts=("The draft is based on instructor-approved lecture notes.",),
        call_to_action="Invite questions after reviewing the course notes.",
    )


def test_agentic_social_review_has_trace_and_preserves_external_action_block() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages) -> str:
        captured["messages"] = list(messages)
        return (
            "The draft is based on instructor-approved lecture notes. "
            "Editor checklist: verify claims, accessibility, consent, and cooldown before approval."
        )

    result = run_agentic_social_media_review(_request(), provider=FakeProvider(responder))
    assert result.generation_enabled
    assert result.editorial_review is not None
    assert result.human_approval_required
    assert result.external_action_blocked
    assert [step.kind for step in result.agent_trace] == [
        SocialMediaStepKind.PLAN,
        SocialMediaStepKind.SYNTHESIS,
        SocialMediaStepKind.GUARDRAIL,
    ]
    assert result.autoeval is not None
    assert result.autoeval["missing_required_elements"] == []
    prompt = " ".join(message.content for message in captured["messages"])
    assert "Never schedule, upload, publish" in prompt
    assert "engagement bait" in prompt


def test_agentic_social_review_degrades_to_deterministic_drafts_when_llm_is_disabled() -> None:
    result = run_agentic_social_media_review(_request(), provider=DisabledProvider())
    assert not result.generation_enabled
    assert result.editorial_review is None
    assert result.autoeval is None
    assert result.package.external_action_blocked
    assert result.agent_trace[-1].kind is SocialMediaStepKind.NOTE
