# Deployment guide

## 1. Local validation

```powershell
Copy-Item .env.example .env
python -m pip install -e ".[dev]"
python scripts/verify_release.py --root .
python -m pytest
python -m ruff check .
docker compose up --build -d
docker compose ps
.\scripts\smoke_test_windows.ps1
```

Visit `http://localhost:8000/docs` for API documentation and `http://localhost:8501` for
the review UI. The API container must first become healthy; the UI then starts. The local SQLite
volume persists tasks between containers. Stop the local stack with `docker compose down`.

## 2. GitHub release workflow

The target repository recorded for this project is
`https://github.com/DrAslamJaved/Axioms_AI_System.git`. Because it is private, deployment
must be completed from a machine authenticated to your GitHub account.

```powershell
$Repo = 'G:\Research\STEM\Axioms_AI_System'
Set-Location $Repo
git init
git branch -M main
git remote add origin https://github.com/DrAslamJaved/Axioms_AI_System.git
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
- Do not expose the Streamlit or FastAPI ports publicly until authenticated access, TLS, and a
  security/privacy review are implemented.

## 4. Local backup and restore drill

Run this only as an identified operator. It creates a **new** backup and verifies
a temporary restored copy; it does not schedule work or overwrite the live database:

```powershell
python scripts\backup_sqlite.py create `
  --source data\axioms.sqlite3 `
  --destination backups\axioms-$(Get-Date -Format yyyy-MM-dd).sqlite3

python scripts\backup_sqlite.py verify-restore `
  --backup backups\axioms-YYYY-MM-DD.sqlite3
```

Store backups outside Git and restrict access according to the institutional
retention and privacy policy. A successful drill validates only SQLite integrity
and the presence of the Axioms task table; it does not approve deployment,
substitute for disaster-recovery planning, or restore data into production.
