from dataclasses import dataclass
from typing import Optional, Dict
import time
import threading

@dataclass
class JobStatus:
    state: str = "queued"        # queued|running|done|error
    stage: str = "queued"        # upload|convert|separate|encode|done|error
    progress: float = 0.0        # 0..100 (best-effort)
    eta_seconds: Optional[int] = None
    message: str = ""
    updated_at: float = 0.0
    error: Optional[str] = None

_jobs: Dict[str, JobStatus] = {}
_lock = threading.Lock()

def create_job(job_id: str) -> None:
    with _lock:
        _jobs[job_id] = JobStatus(updated_at=time.time())

def update_job(job_id: str, **kwargs) -> None:
    with _lock:
        j = _jobs[job_id]
        for k, v in kwargs.items():
            setattr(j, k, v)
        j.updated_at = time.time()

def get_job(job_id: str) -> JobStatus:
    with _lock:
        return _jobs[job_id]
