from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, get_integrations   # Entra JWT -> user
from app.models.jobs import AuditEvent, Job, JobKind, Status, Step
from app.workflows import engine
from app.workflows.onboard import ONBOARD_STEPS
from app.workflows.offboard import OFFBOARD_STEPS

router = APIRouter(prefix="/jobs", tags=["jobs"])
WORKFLOWS = {JobKind.ONBOARD: ONBOARD_STEPS, JobKind.OFFBOARD: OFFBOARD_STEPS}


class OnboardRequest(BaseModel):
    first_name: str
    last_name: str
    office: str                              # NY | FW | UK  -> mappings.offices
    department: str
    job_title: str
    license_skus: list[str]
    manager_sam: str | None = None
    extra_groups: list[str] = []
    needs_workspace: bool = True
    workspace_target: str | None = None      # override office default, e.g. BNY
    adobe_tier: str | None = None            # pro | standard | None


class OffboardRequest(BaseModel):
    sam: str
    incident: str                            # ServiceNow INC######
    access_until: str | None = None          # ISO datetime; end-of-day access
    new_group_owner_sam: str | None = None
    convert_to_shared: bool = True
    forward_to: str | None = None
    auto_reply: str | None = None


@router.post("/onboard", status_code=202)
async def start_onboard(req: OnboardRequest, bg: BackgroundTasks,
                        db: Session = Depends(get_db), user=Depends(current_user)):
    subject = f"{req.first_name} {req.last_name}"          # UPN is derived in ad.create_user
    job = engine.create_job(db, kind=JobKind.ONBOARD, subject_upn=subject,
                            requested_by=user.upn, payload=req.model_dump(),
                            specs=ONBOARD_STEPS)
    bg.add_task(engine.run_job, db, job, ONBOARD_STEPS, get_integrations())
    return {"job_id": job.id}


@router.post("/offboard", status_code=202)
async def start_offboard(req: OffboardRequest, bg: BackgroundTasks,
                         db: Session = Depends(get_db), user=Depends(current_user)):
    job = engine.create_job(db, kind=JobKind.OFFBOARD, subject_upn=req.sam,
                            requested_by=user.upn, payload=req.model_dump(),
                            specs=OFFBOARD_STEPS)
    bg.add_task(engine.run_job, db, job, OFFBOARD_STEPS, get_integrations())
    return {"job_id": job.id}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    return {
        "id": job.id, "kind": job.kind, "status": job.status, "subject": job.subject_upn,
        "requested_by": job.requested_by, "created_at": job.created_at,
        "steps": [{"name": s.name, "system": s.system, "status": s.status,
                   "attempts": s.attempts, "duration_s": s.duration_s,
                   "error": s.error, "output": s.output} for s in job.steps],
    }


@router.post("/{job_id}/steps/{step_name}/retry", status_code=202)
async def retry_step(job_id: str, step_name: str, bg: BackgroundTasks,
                     db: Session = Depends(get_db), user=Depends(current_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    step = next((s for s in job.steps if s.name == step_name), None)
    if not step or step.status != Status.FAILED:
        raise HTTPException(409, "step is not in a failed state")
    step.status, step.attempts = Status.PENDING, 0
    db.add(AuditEvent(actor=user.upn, action="step.retried", job_id=job.id,
                      detail={"step": step_name}))
    db.commit()
    bg.add_task(engine.run_job, db, job, WORKFLOWS[job.kind], get_integrations(),
                only_step=step_name)
    return {"job_id": job.id, "step": step_name}


@router.get("/metrics/summary")
def metrics(db: Session = Depends(get_db), user=Depends(current_user)):
    """Feeds the operational-excellence dashboard."""
    total = db.scalar(select(func.count(Job.id))) or 0
    ok = db.scalar(select(func.count(Job.id)).where(Job.status == Status.SUCCEEDED)) or 0
    fails_by_system = db.execute(
        select(Step.system, func.count(Step.id))
        .where(Step.status == Status.FAILED).group_by(Step.system)
    ).all()
    avg_by_step = db.execute(
        select(Step.name, func.avg(func.julianday(Step.finished_at) - func.julianday(Step.started_at)))
        .where(Step.status == Status.SUCCEEDED).group_by(Step.name)
    ).all()   # julianday = SQLite; swap for EXTRACT(EPOCH …) on Postgres
    return {
        "jobs_total": total,
        "success_rate": (ok / total) if total else None,
        "failed_steps_by_system": dict(fails_by_system),
        "avg_step_days": dict(avg_by_step),
    }
