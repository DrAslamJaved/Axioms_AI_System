from pathlib import Path

from scripts.verify_release import verify_release


def test_current_repository_passes_release_structure_verification() -> None:
    root = Path(__file__).parents[1]
    assert verify_release(root) == []


def test_release_verifier_rejects_missing_controls(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("AXIOMS_LLM_PROVIDER=enabled\n", encoding="utf-8")
    errors = verify_release(tmp_path)
    assert any("Missing required file" in error for error in errors)
    assert any("disabled" in error for error in errors)


def test_release_verifier_requires_an_explicitly_safe_auth_default(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(
        "AXIOMS_LLM_PROVIDER=disabled\nAXIOMS_REQUIRE_AUTH=true\n", encoding="utf-8"
    )
    errors = verify_release(tmp_path)
    assert any("AXIOMS_REQUIRE_AUTH=false" in error for error in errors)
