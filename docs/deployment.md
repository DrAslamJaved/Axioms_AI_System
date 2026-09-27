# Deployment guide

## 1. Local validation

```bash
copy .env.example .env  # Windows PowerShell/cmd
# or: cp .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -e ".[dev]"
pytest
ruff check .
docker compose up --build
```

Visit `http://localhost:8000/docs` for API documentation and `http://localhost:8501` for
the review UI. The local SQLite volume persists tasks between containers.

## 2. GitHub release workflow

The target repository recorded for this project is
`https://github.com/DrAslamJaved/Axioms_IRFS17.git`. Because it is private, deployment
must be completed from a machine authenticated to your GitHub account.

```powershell
$Repo = 'G:\Research\STEM\Axioms_IFRS17'
Set-Location $Repo
git init
git branch -M main
git remote add origin https://github.com/DrAslamJaved/Axioms_IRFS17.git
git add .
git commit -m "feat: add human-governed Axioms foundation MVP"
git push -u origin main
```

If the repository already contains a README or other files, clone it first, copy this
starter into that clone, review `git status`, commit on a feature branch, and open a pull
request. Do not force-push or overwrite existing work.

## 3. Production prerequisites

- Replace the local SQLite database with a managed encrypted database and tested backup.
- Set secrets in the hosting provider; never in `.env` committed to Git.
- Keep `AXIOMS_LLM_PROVIDER=disabled` until provider, spending limit, logging, and tests
  have been approved.
- Put the service behind TLS and authenticated access.
- Complete a data-retention policy before uploading lecture, paper, or student materials.
- Exercise backup/restore and approval-gate tests before inviting other users.

