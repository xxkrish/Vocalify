import uuid
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.jobs import create_job, update_job, get_job
from app.services.demucs_runner import run_demucs_with_progress

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
TMP_DIR = BASE_DIR.parent / "tmp"

STORAGE_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for portfolio
    allow_methods=["*"],
    allow_headers=["*"],
)


def _worker(job_id: str, input_path: Path, job_dir: Path):
    try:
        update_job(job_id, state="running", stage="starting", progress=1.0, message="Starting…", eta_seconds=None)

        def on_progress(pct: float, stage: str, eta: int | None, msg: str):
            update_job(
                job_id,
                state="running" if stage != "done" else "done",
                stage=stage,
                progress=float(pct),
                eta_seconds=eta,
                message=msg,
            )

        run_demucs_with_progress(
            input_path=input_path,
            job_dir=job_dir,
            on_progress=on_progress,
        )

        update_job(job_id, state="done", stage="done", progress=100.0, message="Done ✅", eta_seconds=0)

    except Exception as e:
        update_job(job_id, state="error", stage="error", progress=0.0, message="Error", error=str(e))
    finally:
        if input_path.exists():
            input_path.unlink(missing_ok=True)


@app.post("/api/jobs")
async def start_job(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file uploaded")

    job_id = str(uuid.uuid4())[:8]
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    create_job(job_id)

    input_path = TMP_DIR / f"{job_id}_{file.filename}"
    input_path.write_bytes(await file.read())

    t = Thread(target=_worker, args=(job_id, input_path, job_dir), daemon=True)
    t.start()

    return {
        "jobId": job_id,
        "statusUrl": f"/api/jobs/{job_id}",
        "vocalsUrl": f"/api/download/{job_id}/vocals",
        "instrumentalUrl": f"/api/download/{job_id}/instrumental",
    }


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    st = get_job(job_id)
    if not st:
        raise HTTPException(404, "Job not found")
    return st


@app.get("/api/download/{job_id}/{stem}")
def download(job_id: str, stem: str):
    job_dir = STORAGE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")

    if stem == "vocals":
        path = job_dir / "vocals_320.mp3"
        name = "vocals_320.mp3"
    elif stem == "instrumental":
        path = job_dir / "instrumental_320.mp3"
        name = "instrumental_320.mp3"
    else:
        raise HTTPException(400, "Invalid stem")

    if not path.exists():
        raise HTTPException(404, "File not ready")

    return FileResponse(path, filename=name, media_type="audio/mpeg")
