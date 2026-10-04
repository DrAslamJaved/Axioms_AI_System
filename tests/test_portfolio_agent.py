from pathlib import Path

import pytest
from docx import Document

from axioms.llm import DisabledProvider, FakeProvider, LLMMessage
from axioms.portfolio_agent import (
    DataAccessLevel,
    DatasetAsset,
    PortfolioAudience,
    PortfolioEvidence,
    PortfolioRequest,
    RepositoryVisibility,
    build_portfolio_package,
    export_docx,
)


def request() -> PortfolioRequest:
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


def test_portfolio_package_is_evidence_bound_and_cannot_publish_to_github() -> None:
    package = build_portfolio_package(request())
    assert package.approval_required
    assert package.github_action_blocked
    assert "[E01]" in package.readme_sections[1].guidance
    assert any(item.path == "tests/" for item in package.repository_structure)



def test_disabled_llm_retains_the_deterministic_portfolio_package() -> None:
    baseline = build_portfolio_package(request())
    package = build_portfolio_package(request(), provider=DisabledProvider())
    assert package == baseline


def test_fake_llm_enriches_internal_repository_purposes_without_changing_controls() -> None:
    captured: dict[str, list[LLMMessage]] = {}

    def responder(messages: list[LLMMessage]) -> str:
        captured["messages"] = messages
        return "---".join(
            f"Internal portfolio-planning guidance for repository item {number}; preserve verification and release review."
            for number in range(1, 12)
        )

    baseline = build_portfolio_package(request(), provider=DisabledProvider())
    package = build_portfolio_package(request(), provider=FakeProvider(responder))

    assert [item.path for item in package.repository_structure] == [
        item.path for item in baseline.repository_structure
    ]
    assert package.readme_sections == baseline.readme_sections
    assert package.reproducibility_checklist == baseline.reproducibility_checklist
    assert package.impact_summary == baseline.impact_summary
    assert package.publication_checks == baseline.publication_checks
    assert package.approval_required
    assert package.github_action_blocked
    assert package.repository_structure[0].purpose.startswith("Internal portfolio-planning guidance")
    prompt = " ".join(message.content for message in captured["messages"])
    assert "[E01]" in prompt
    assert "Small public teaching graph" in prompt
    assert "not write a README" in prompt
    assert "testing-before-publication" in prompt


def test_malformed_or_failed_llm_output_retains_the_deterministic_portfolio_package() -> None:
    baseline = build_portfolio_package(request(), provider=DisabledProvider())
    malformed = build_portfolio_package(request(), provider=FakeProvider(lambda _messages: "one purpose only"))

    class BrokenProvider:
        name = "broken"

        def complete(self, messages, *, max_tokens: int = 1024, temperature: float = 0.2):
            raise RuntimeError("provider unavailable")

    failed = build_portfolio_package(request(), provider=BrokenProvider())
    assert malformed == baseline
    assert failed == baseline


def test_public_package_rejects_proprietary_data() -> None:
    blocked = PortfolioRequest(
        **{
            field: getattr(request(), field)
            for field in (
                "project_title",
                "research_summary",
                "target_audience",
                "repository_visibility",
                "verified_evidence",
                "include_demo_plan",
                "include_notebook_plan",
            )
        },
        dataset_assets=(
            DatasetAsset(name="Private laboratory data", access_level=DataAccessLevel.PROPRIETARY),
        ),
    )
    with pytest.raises(ValueError, match="proprietary"):
        build_portfolio_package(blocked)


def test_portfolio_docx_contains_project_title(tmp_path: Path) -> None:
    destination = export_docx(build_portfolio_package(request()), tmp_path / "portfolio_package.docx")
    document = Document(destination)
    assert destination.exists()
    assert "Agentic Spectral Graph Theory" in document.paragraphs[0].text
