"""Persistent jobs using the application's SQLAlchemy engine. Inputs/secrets are never stored."""
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import os
from uuid import uuid4
from fastapi import Header, HTTPException
from sqlalchemy import Column, String, Text, Table, MetaData, select, update
from .schemas import AnalysisJob

metadata = MetaData()
jobs = Table("product_understanding_jobs", metadata,
    Column("analysis_id", String(64), primary_key=True), Column("owner", String(64), nullable=False),
    Column("kind", String(16), nullable=False), Column("status", String(16), nullable=False),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False),
    Column("payload", Text, nullable=False))


def authorize(authorization: str | None = Header(default=None)) -> str:
    expected = os.getenv("UNDERSTANDING_API_KEY", "")
    if not expected:
        raise HTTPException(503, "Product understanding API is not configured")
    supplied = (authorization or "").removeprefix("Bearer ")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Authentication required")
    return hashlib.sha256(expected.encode()).hexdigest()


class JobStore:
    def __init__(self, engine):
        self.engine = engine
        metadata.create_all(engine)

    def create(self, kind, owner):
        now = datetime.now(timezone.utc).isoformat()
        job = AnalysisJob(analysis_id=uuid4().hex, kind=kind, status="PENDING", created_at=now, updated_at=now)
        with self.engine.begin() as db:
            db.execute(jobs.insert().values(analysis_id=job.analysis_id, owner=owner, kind=kind,
                status=job.status.value, created_at=now, updated_at=now, payload=job.model_dump_json()))
        return job

    def save(self, job):
        job.updated_at = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as db:
            db.execute(update(jobs).where(jobs.c.analysis_id == job.analysis_id).values(
                status=job.status, updated_at=job.updated_at, payload=job.model_dump_json()))

    def get(self, analysis_id, kind, owner):
        with self.engine.begin() as db:
            payload = db.execute(select(jobs.c.payload).where(jobs.c.analysis_id == analysis_id,
                jobs.c.kind == kind, jobs.c.owner == owner)).scalar_one_or_none()
        if payload is None:
            raise HTTPException(404, "Analysis not found")
        job = AnalysisJob.model_validate_json(payload)
        if job.status in ("PENDING", "RUNNING") and datetime.fromisoformat(job.updated_at) < datetime.now(timezone.utc) - timedelta(minutes=15):
            job.status = "FAILED"
            job.error = "Analysis interrupted or expired; submit a new request."
            self.save(job)
        return job

    def run(self, job, analyze):
        job.status = "RUNNING"
        self.save(job)
        try:
            result = analyze()
            setattr(job, f"{job.kind}_analysis", result)
            job.status = "COMPLETED"
        except Exception:
            # Exceptions can contain local paths, URL credentials, and source excerpts.
            job.status = "FAILED"
            job.error = "Analysis could not complete safely. Check access and input, then retry."
        self.save(job)


def get_store():
    from app.db.session import engine
    return JobStore(engine)
