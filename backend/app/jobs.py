from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import Lock
from typing import Dict, Optional


@dataclass
class JobStatus:
    job_id: str
    state: str  # "queued" | "running" | "done" | "error"
    stage: str  # "starting" | "downloading" | "separating" | "finalizing" | ...
    progress: float  # 0..100
    message: str
    eta_seconds: Optional[int] = None
    error: Optional[str] = None


_lock = Lock()
_jobs: Dict[str, JobStatus] = {}


def create_job(job_id: str) -> JobStatus:
    st = JobStatus(
        job_id=job_id,
        state="queued",
        stage="starting",
        progress=0.0,
        message="Queued…",
        eta_seconds=None,
        error=None,
    )
    with _lock:
        _jobs[job_id] = st
    return st


def update_job(job_id: str, **kwargs) -> JobStatus:
    with _lock:
        if job_id not in _jobs:
            # allow late creation if needed
            _jobs[job_id] = JobStatus(
                job_id=job_id,
                state="queued",
                stage="starting",
                progress=0.0,
                message="Queued…",
            )
        st = _jobs[job_id]
        for k, v in kwargs.items():
            if hasattr(st, k):
                setattr(st, k, v)
        _jobs[job_id] = st
        return st


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        st = _jobs.get(job_id)
        return asdict(st) if st else None
