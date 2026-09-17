#Lifecycle Console

Python/FastAPI service that runs onboarding and offboarding as auditable, retryable
jobs across Active Directory, Microsoft Graph/Entra, Exchange Online, AWS WorkSpaces
and Adobe — replacing the PowerShell scripts in `Codes/`. Hosted in Azure, versioned
in Azure DevOps.

## What's in this zip

```
oha-lifecycle/
  README.md                      <- you are here
  azure-pipelines.yml            <- CI: lint+test -> build image -> deploy to Container Apps
  .gitignore
  docs/
    REQUIREMENTS.md              <- everything you must provide (secrets, IDs, decisions)
    SCRIPT_MAPPING.md            <- which old script became which step/endpoint
  backend/
    app/
      main.py                    <- FastAPI app, mounts routers
      db.py, deps.py, config.py  <- DB session, Entra JWT auth + roles, mappings loader
      models/jobs.py             <- Job / Step / AuditEvent tables
      workflows/engine.py        <- step runner: persist, retry, resume one step
      workflows/onboard.py       <- 8 onboarding steps
      workflows/offboard.py      <- 11 offboarding steps
      api/jobs.py                <- POST /jobs/onboard, /jobs/offboard, retry, metrics
      api/utilities.py           <- calendar perms, group reports, reassign owner, Adobe seats
      integrations/*.py          <- one client per system (method signatures; bodies TODO)
    config/mappings.yaml         <- offices, OUs, groups, DLs, WorkSpaces targets, Adobe profiles
    tests/test_engine.py         <- proves the engine without any external system
    requirements*.txt, Dockerfile, .env.example
  agent/README.md                <- the Windows PowerShell worker for EXO-only cmdlets
  infra/README.md                <- Terraform scope
  frontend/                      <- Next.js app (not yet scaffolded; mockup is in Claude)
```

## Run it locally in 5 minutes

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                                    # DEV_BYPASS_AUTH=true is already set
set -a; source .env; set +a                             # Windows: use dotenv or set vars manually
pytest                                                  # engine test should pass
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs. `POST /jobs/onboard` will create a job and fail on the
first step with `NotImplementedError` — that's expected until the AD client is written.
The job, its steps and the audit row are all in `lifecycle.db`.

## Order of work

1. **Rotate the Adobe UMAPI secret** that was in `Codes/Adobe/.env`. It travelled in a zip.
2. Work through `docs/REQUIREMENTS.md`. Put secrets in Key Vault, non-secrets in
   `config/mappings.yaml` (already pre-filled from your scripts; grep `CONFIRM`).
3. Implement `integrations/ad.py` first — both workflows depend on it. `ldap3` if the
   app can reach a DC; otherwise proxy to the Windows agent and keep PowerShell.
4. Stand up the Windows agent (`agent/`) with app-only EXO auth. Port
   `NewUser-Exchange.ps1` and the calendar scripts into its endpoints.
5. `graph.py` (msal + httpx), `aws_workspaces.py` (boto3 assume-role), `adobe.py`
   (UMAPI v2), `signature.py` (python-docx).
6. Create the Azure DevOps project, both service connections, the Key Vault variable
   group and the `prod` environment. Push; the pipeline runs.
7. Front end: Next.js + MSAL against `/jobs` and `/utilities`. The three mockup screens
   (dashboard, onboarding wizard, job detail) are the spec.

## Conventions

- Every step is **idempotent**: `ensure_*` methods return the existing object instead of
  failing on "already exists". That's what makes the Retry button safe.
- Step **output** is persisted and feeds the dashboard; the initial password is placed in
  `ctx.transient` and shown once, never stored.
- `continue_on_failure=True` on steps that shouldn't block the rest (Adobe, signature,
  Exchange); AD and license steps block.
- All config that can change without a code change lives in `mappings.yaml` and goes
  through a PR.
# lifecycle
