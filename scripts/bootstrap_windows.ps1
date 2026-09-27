param(
    [string]$RepositoryPath = "G:\Research\STEM\Axioms_IFRS17"
)

$ErrorActionPreference = "Stop"
Set-Location $RepositoryPath

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .

Write-Host "Validated. Start locally with: docker compose up --build"
