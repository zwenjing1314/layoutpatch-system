"""Latest job state plus immutable-on-retry attempt snapshots."""
from backend.db.connection import ROOT
from backend.db.models import JobAttempt

TERMINAL = frozenset(("failed", "interrupted", "completed", "cancelled"))
MAX_ATTEMPTS = 10


def sync_attempt(db, job):
    record = db.get(JobAttempt, (job.id, job.attempt))
    if record is None:
        record = JobAttempt(job_id=job.id, attempt=job.attempt, created_at=job.updated_at)
        db.add(record)
    for key in ("status", "stage", "progress", "error_code", "cancel_requested_at", "updated_at"):
        setattr(record, key, getattr(job, key))
    if job.status == "running" and record.started_at is None:
        record.started_at = job.updated_at
    if job.status in TERMINAL:
        record.ended_at = job.updated_at
    return record


def retry_source(version):
    try:
        path = (ROOT / version.pdf_path).resolve()
        return path if path.is_relative_to((ROOT / "runtime").resolve()) and path.is_file() else None
    except (OSError, RuntimeError):
        return None


def retry_available(job, version, document):
    return (job.status in TERMINAL - {"completed"} and job.attempt < MAX_ATTEMPTS
            and document.status == "registered" and document.active_version_id is None
            and retry_source(version) is not None)
