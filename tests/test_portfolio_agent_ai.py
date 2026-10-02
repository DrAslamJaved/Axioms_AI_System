from axioms.llm import DisabledProvider, FakeProvider, LLMMessage
from axioms.portfolio_agent import (
    DataAccessLevel,
    DatasetAsset,
    PortfolioAudience,
    PortfolioEvidence,
    PortfolioRequest,
    RepositoryVisibility,
)
from axioms.portfolio_agent_ai import PortfolioStepKind, run_agentic_portfolio_review


def _request() -> PortfolioRequest:
    return PortfolioRequest(
        project_title="Agentic Spectral Graph Theory Learning Toolkit",
        research_summary="A reproducible toolkit for explaining spectral graph theory concepts.",
        target_audience=PortfolioAudience.BOTH,
        repository_visibility=RepositoryVisibility.PUBLIC,
        verified_evidence=(
            PortfolioEvidence(
                evidence_id="E01",
                claim="The toolkit is based on instructor-approved lecture notes.",
                source_reference="Internal course-material review record",
                verified=True,
            ),
        ),
        dataset_assets=(
            DatasetAsset(
                name="Small public teaching graph",
                access_level=DataAccessLevel.PUBLIC,
                licence_or_permission="CC BY 4.0",
                attribution="Teaching graph author record",
            ),
        ),
    )


def test_agentic_portfolio_review_has_trace_and_preserves_github_block() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages) -> str:
        captured["messages"] = list(messages)
        return "[E01] is traceable. Researcher checklist: verify data permissions before human approval."

    result = run_agentic_portfolio_review(_request(), provider=FakeProvider(responder))
    assert result.generation_enabled
    assert result.portfolio_review is not None
    assert result.human_approval_required
    assert result.github_action_blocked
    assert [step.kind for step in result.agent_trace] == [
        PortfolioStepKind.PLAN,
        PortfolioStepKind.SYNTHESIS,
        PortfolioStepKind.GUARDRAIL,
    ]
    assert result.autoeval is not None
    assert result.autoeval["missing_required_elements"] == []
    prompt = " ".join(message.content for message in captured["messages"])
    assert "Do not create repositories" in prompt
    assert "[E01]" in prompt


def test_agentic_portfolio_review_degrades_to_deterministic_package_when_llm_is_disabled() -> None:
    result = run_agentic_portfolio_review(_request(), provider=DisabledProvider())
    assert not result.generation_enabled
    assert result.portfolio_review is None
    assert result.autoeval is None
    assert result.package.github_action_blocked
    assert result.agent_trace[-1].kind is PortfolioStepKind.NOTE
