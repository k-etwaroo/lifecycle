"""Job / Step / Audit tables. Every onboarding or offboarding run is one Job
made of ordered Steps. The step rows are what the ops dashboard reads."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class JobKind(str, enum.Enum):
    ONBOARD = "onboard"
    OFFBOARD = "offboard"


class Status(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[JobKind] = mapped_column(Enum(JobKind))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING)
    subject_upn: Mapped[str] = mapped_column(String(255), index=True)   # who is being on/offboarded
    requested_by: Mapped[str] = mapped_column(String(255))             # tech's UPN from Entra token
    payload: Mapped[dict] = mapped_column(JSON)                         # wizard input (name, dept, licenses…)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["Step"]] = relationship(back_populates="job", order_by="Step.order")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))        # e.g. "ad.create_user"
    system: Mapped[str] = mapped_column(String(40))       # ad | graph | aws | adobe | exo
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict | None] = mapped_column(JSON)     # what the step produced (ids, sids…)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[Job] = relationship(back_populates="steps")

    @property
    def duration_s(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100))      # job.created, step.retried, …
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    detail: Mapped[dict | None] = mapped_column(JSON)
