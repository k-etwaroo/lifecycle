"""Generic step engine. Workflows (onboard.py / offboard.py) are just ordered
lists of StepSpec. The runner persists state after every step so a failed run
can be resumed or a single step retried from the UI."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.models.jobs import AuditEvent, Job, Status, Step, utcnow

log = logging.getLogger(__name__)


@dataclass
class Context:
    """Shared state passed through every step. Steps read the payload and
    write results into `outputs` so later steps can use them
    (e.g. ad.create_user -> sid, graph.assign_license needs the UPN)."""
    job: Job
    payload: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    integrations: dict[str, Any] = field(default_factory=dict)   # injected clients
    transient: dict[str, Any] = field(default_factory=dict)      # shown once, never persisted (initial password)


StepFn = Callable[[Context], Awaitable[dict[str, Any] | None]]


@dataclass
class StepSpec:
    name: str                      # "ad.create_user"
    system: str                    # "ad"
    run: StepFn
    max_attempts: int = 3
    continue_on_failure: bool = False   # e.g. Adobe failing shouldn't block the rest
    when: Callable[[Context], bool] | None = None   # skip condition


class StepFailed(Exception):
    pass


def create_job(db: Session, *, kind, subject_upn: str, requested_by: str,
               payload: dict, specs: list[StepSpec]) -> Job:
    job = Job(kind=kind, subject_upn=subject_upn, requested_by=requested_by, payload=payload)
    for i, spec in enumerate(specs):
        job.steps.append(Step(order=i, name=spec.name, system=spec.system))
    db.add(job)
    db.add(AuditEvent(actor=requested_by, action="job.created", job_id=job.id,
                      detail={"kind": kind, "subject": subject_upn}))
    db.commit()
    return job


async def run_job(db: Session, job: Job, specs: list[StepSpec],
                  integrations: dict[str, Any], *, only_step: str | None = None) -> Job:
    """Execute pending/failed steps in order. `only_step` retries one step."""
    spec_by_name = {s.name: s for s in specs}
    ctx = Context(job=job, payload=job.payload, integrations=integrations)

    # rehydrate outputs from already-succeeded steps so retries have context
    for st in job.steps:
        if st.status == Status.SUCCEEDED and st.output:
            ctx.outputs[st.name] = st.output

    job.status = Status.RUNNING
    job.started_at = job.started_at or utcnow()
    db.commit()

    for st in job.steps:
        if only_step and st.name != only_step:
            continue
        if st.status == Status.SUCCEEDED:
            continue
        spec = spec_by_name[st.name]

        if spec.when and not spec.when(ctx):
            st.status = Status.SKIPPED
            db.commit()
            continue

        ok = await _run_step(db, st, spec, ctx)
        if not ok and not spec.continue_on_failure:
            job.status = Status.FAILED
            job.finished_at = utcnow()
            db.commit()
            return job

    job.status = (Status.FAILED if any(s.status == Status.FAILED for s in job.steps)
                  else Status.SUCCEEDED)
    job.finished_at = utcnow()
    db.commit()
    return job


async def _run_step(db: Session, st: Step, spec: StepSpec, ctx: Context) -> bool:
    st.status = Status.RUNNING
    st.started_at = utcnow()
    st.error = None
    db.commit()

    while st.attempts < spec.max_attempts:
        st.attempts += 1
        try:
            result = await spec.run(ctx) or {}
            st.output = result
            ctx.outputs[spec.name] = result
            st.status = Status.SUCCEEDED
            st.finished_at = utcnow()
            db.commit()
            log.info("step ok %s (%.1fs)", spec.name, st.duration_s or 0)
            return True
        except Exception as exc:          # noqa: BLE001 – we want everything recorded
            st.error = f"{type(exc).__name__}: {exc}"
            log.warning("step %s attempt %d failed: %s", spec.name, st.attempts, exc)
            db.commit()

    st.status = Status.FAILED
    st.finished_at = utcnow()
    db.commit()
    return False
