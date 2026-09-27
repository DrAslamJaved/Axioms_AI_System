from pathlib import Path

import pytest
from docx import Document

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
