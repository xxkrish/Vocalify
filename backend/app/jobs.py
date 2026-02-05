from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import json
import time

def _job_file(job_dir: Path) -> Path:
    return job_dir / "job.json"

def create_job(job_dir: Path, filename: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {
        "status": "queued",     # queued | running | done | failed
        "progress": 0.0,        # 0..100
        "etaSeconds": None,
        "message": "Queued",
        "filename": filename,
        "createdAt": int(time.time()),
        "updatedAt": int(time.time()),
        "error": None,
    }
    _job_file(job_dir).write_text(json.dumps(data), encoding="utf-8")

def update_job(job_dir: Path, **updates: Any) -> None:
    path = _job_file(job_dir)
    data: Dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.update(updates)
    data["updatedAt"] = int(time.time())
    path.write_text(json.dumps(data), encoding="utf-8")

def get_job(job_dir: Path) -> Dict[str, Any]:
    path = _job_file(job_dir)
    if not path.exists():
        raise FileNotFoundError("job.json not found")
    return json.loads(path.read_text(encoding="utf-8"))
