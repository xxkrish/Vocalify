import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.services.demucs_runner import run_demucs
from app.jobs import create_job, update_job, get_job

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
TMP_DIR = BASE_DIR.parent / "tmp"

STORAGE_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job_dir = STORAGE_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")
    try:
        return get_job(job_dir)
    except FileNotFoundError:
        raise HTTPException(404, "Job not initialized")

@app.post("/api/separate")
async def separate(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file uploaded")

    job_id = str(uuid.uuid4())[:8]
    job_dir = STORAGE_DIR / job_id
    create_job(job_dir, filename=file.filename)

    input_path = TMP_DIR / f"{job_id}_{file.filename}"
    input_path.write_bytes(await file.read())

    def on_progress(pct: float, eta: int | None, msg: str):
        update_job(job_dir, status="running", progress=pct, etaSeconds=eta, message=msg)

    try:
        update_job(job_dir, status="running", progress=1.0, message="Preparing…")
        run_demucs(input_path=input_path, job_dir=job_dir, on_progress=on_progress)
        update_job(job_dir, status="done", progress=100.0, etaSeconds=0, message="Done ✅")
    except Exception as e:
        update_job(job_dir, status="failed", error=str(e), message="Failed")
        raise HTTPException(500, f"Separation failed: {e}")
    finally:
        if input_path.exists():
            input_path.unlink()

    return {
        "jobId": job_id,
        "vocalsUrl": f"/api/download/{job_id}/vocals",
        "instrumentalUrl": f"/api/download/{job_id}/instrumental",
    }

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
