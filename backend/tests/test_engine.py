"""Runs the step engine against fake integrations — no AD/Graph/AWS needed."""
import asyncio
from app.db import init_db, SessionLocal
from app.models.jobs import JobKind, Status
from app.workflows import engine
from app.workflows.engine import StepSpec


async def ok(ctx): return {"ran": True}
async def boom(ctx): raise RuntimeError("nope")


def test_retry_then_fail():
    init_db()
    db = SessionLocal()
    specs = [StepSpec("a", "x", ok), StepSpec("b", "x", boom, max_attempts=2), StepSpec("c", "x", ok)]
    job = engine.create_job(db, kind=JobKind.ONBOARD, subject_upn="t", requested_by="t", payload={}, specs=specs)
    asyncio.run(engine.run_job(db, job, specs, {}))
    assert job.status == Status.FAILED
    assert [s.status for s in job.steps] == [Status.SUCCEEDED, Status.FAILED, Status.PENDING]
    assert job.steps[1].attempts == 2
