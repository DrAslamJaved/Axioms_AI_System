"""Fail-fast structural preflight for a local Axioms release package."""
from __future__ import annotations

import argparse
from pathlib import Path

REQUIRED_FILES = (
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "README.md",
    "docker-compose.yml",
    "docs/deployment.md",
    "axioms/api.py",
    "streamlit_app.py",
)


def verify_release(root: Path) -> list[str]:
    """Return structural errors without starting containers or contacting external services."""
    errors = [f"Missing required file: {path}" for path in REQUIRED_FILES if not (root / path).is_file()]
    env_path = root / ".env.example"
    if env_path.is_file() and "AXIOMS_LLM_PROVIDER=disabled" not in env_path.read_text(encoding="utf-8"):
        errors.append(".env.example must keep AXIOMS_LLM_PROVIDER=disabled for the MVP.")
    if env_path.is_file() and "AXIOMS_REQUIRE_AUTH=false" not in env_path.read_text(encoding="utf-8"):
        errors.append(".env.example must keep AXIOMS_REQUIRE_AUTH=false for local development.")
    compose_path = root / "docker-compose.yml"
    if compose_path.is_file():
        compose = compose_path.read_text(encoding="utf-8")
        for required_fragment in ("healthcheck:", "condition: service_healthy", "axioms_data:"):
            if required_fragment not in compose:
                errors.append(f"docker-compose.yml is missing required release control: {required_fragment}")
    deployment_path = root / "docs/deployment.md"
    if deployment_path.is_file() and "Axioms_AI_System" not in deployment_path.read_text(encoding="utf-8"):
        errors.append("docs/deployment.md must identify the Axioms_AI_System repository path.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root to verify.")
    args = parser.parse_args()
    errors = verify_release(args.root.resolve())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: local release structure and conservative defaults are verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
