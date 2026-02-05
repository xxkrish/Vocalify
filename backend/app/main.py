import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.jobs import create_job, update_job, get_job
from app.services.demucs_runner import run_demucs

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
TMP_DIR = BASE_DIR.parent / "tmp"

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev; restrict later for Vercel
    allow_methods=["*"],
    allow_headers=["*"],
)

def _sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).strip()
    safe = safe.replace(" ", "_")
    return safe or "audio"

@app.post("/api/jobs")
async def create_separation_job(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file uploaded")

    job_id = uuid.uuid4().hex[:8]
    create_job(job_id)

    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_filename(file.filename)
    input_path = TMP_DIR / f"{job_id}_{safe_name}"
    input_path.write_bytes(await file.read())

    update_job(
        job_id,
        state="running",
        stage="queued",
        progress=0.0,
        eta_seconds=None,
        message="Queued…",
        error=None,
    )

    def worker():
        try:
            def on_progress(pct: float, eta: int | None, msg: str):
                # clamp 0..100
                pct = max(0.0, min(100.0, float(pct)))
                update_job(
                    job_id,
                    state="running",
                    stage="separate",
                    progress=pct,
                    eta_seconds=eta,
                    message=msg,
                    error=None,
                )

            # run demucs with progress callback
            run_demucs(
                input_path=input_path,
                job_dir=job_dir,
                on_progress=on_progress,
            )

            update_job(
                job_id,
                state="done",
                stage="done",
                progress=100.0,
                eta_seconds=0,
                message="Done ✅",
                error=None,
            )

        except Exception as e:
            update_job(
                job_id,
                state="error",
                stage="error",
                progress=0.0,
                eta_seconds=None,
                message="Failed",
                error=str(e),
            )
        finally:
            try:
                if input_path.exists():
                    input_path.unlink()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()

    return {
        "jobId": job_id,
        "statusUrl": f"/api/jobs/{job_id}",
        "vocalsUrl": f"/api/download/{job_id}/vocals",
        "instrumentalUrl": f"/api/download/{job_id}/instrumental",
    }

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    try:
        j = get_job(job_id)
        return j.__dict__
    except KeyError:
        raise HTTPException(404, "Job not found")

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
