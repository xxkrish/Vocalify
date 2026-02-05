import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

# Matches lines like: " 45%|####...| 36.1M/80.2M [00:02<00:02, 20.0MB/s]"
RE_PERCENT = re.compile(r"(\d{1,3})%\|")
RE_ETA = re.compile(r"<(\d{2}):(\d{2})")  # <MM:SS
RE_STAGE_HINT = re.compile(r"(Downloading|Separating|Applying|Loading)", re.IGNORECASE)


def _parse_eta_seconds(line: str) -> Optional[int]:
    m = RE_ETA.search(line)
    if not m:
        return None
    mm = int(m.group(1))
    ss = int(m.group(2))
    return mm * 60 + ss


def run_demucs_with_progress(
    *,
    input_path: Path,
    job_dir: Path,
    on_progress: Callable[[float, str, Optional[int], str], None],
    model: str = "htdemucs_ft",
    bitrate: str = "320",
) -> None:
    """
    Calls on_progress(progress, stage, eta_seconds, message)
    """
    out_dir = job_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        model,
        "--two-stems=vocals",
        "--mp3",
        "--mp3-bitrate",
        bitrate,
        "-o",
        str(out_dir),
        str(input_path),
    ]

    # Start at 1% so UI doesn't look stuck instantly
    on_progress(1.0, "starting", None, "Starting Demucs…")

    # We stream stderr because tqdm usually writes there
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    last_pct = 1.0
    last_stage = "starting"

    def handle_line(line: str):
        nonlocal last_pct, last_stage
        line = line.strip()
        if not line:
            return

        # stage hints
        if "Selected model is a bag of" in line:
            last_stage = "starting"
            on_progress(max(last_pct, 2.0), last_stage, None, "Loading model…")
            return

        if "Downloading" in line or "Downloading:" in line:
            last_stage = "downloading"
            on_progress(max(last_pct, 3.0), last_stage, _parse_eta_seconds(line), "Downloading model files…")
            return

        if "Separating track" in line:
            last_stage = "separating"
            on_progress(max(last_pct, 5.0), last_stage, None, "Separating stems…")
            return

        # tqdm percentage
        pm = RE_PERCENT.search(line)
        if pm:
            pct = float(pm.group(1))
            eta = _parse_eta_seconds(line)
            # keep it monotonic
            if pct < last_pct:
                pct = last_pct
            last_pct = pct
            stage = last_stage if last_stage != "starting" else "separating"
            on_progress(pct, stage, eta, "Processing…")
            return

        # fallback stage detection
        hm = RE_STAGE_HINT.search(line)
        if hm:
            last_stage = hm.group(1).lower()
            on_progress(last_pct, last_stage, _parse_eta_seconds(line), line[:80])
            return

    # Read stderr live
    assert p.stderr is not None
    for line in p.stderr:
        handle_line(line)

    rc = p.wait()
    if rc != 0:
        out = ""
        if p.stdout:
            out += p.stdout.read() if hasattr(p.stdout, "read") else ""
        raise RuntimeError(out or f"demucs failed with code {rc}")

    # finalize outputs
    on_progress(95.0, "finalizing", None, "Finalizing output files…")

    vocals = list(out_dir.glob("**/vocals.mp3"))
    inst = list(out_dir.glob("**/no_vocals.mp3"))
    if not vocals or not inst:
        raise RuntimeError("Outputs not found after demucs run")

    vocals_path = max(vocals, key=lambda x: x.stat().st_mtime)
    inst_path = max(inst, key=lambda x: x.stat().st_mtime)

    shutil.copy(vocals_path, job_dir / "vocals_320.mp3")
    shutil.copy(inst_path, job_dir / "instrumental_320.mp3")

    on_progress(100.0, "done", 0, "Done ✅")
