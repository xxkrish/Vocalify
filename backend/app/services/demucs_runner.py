import shutil
import subprocess
import sys
import time
import re
from pathlib import Path
from typing import Callable, Optional

PROGRESS_RE = re.compile(r"(\d+)%")

def run_demucs(
    input_path: Path,
    job_dir: Path,
    model: str = "htdemucs_ft",
    bitrate: str = "320",
    on_progress: Optional[Callable[[float, int | None, str], None]] = None,
) -> None:
    """
    Runs demucs and reports stable overall progress.
    on_progress(progress_pct, eta_seconds, message)
    """

    out_dir = job_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--two-stems=vocals",
        "--mp3",
        "--mp3-bitrate", bitrate,
        "-o", str(out_dir),
        str(input_path),
    ]

    start_time = time.time()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    # We only start counting progress after separation begins
    started = False

    # Demucs "bag of 4 models" -> multiple progress bars.
    # We'll treat each 0..100 bar as one "phase" and map to overall 0..100.
    phases_total = 4  # good default for htdemucs_ft
    phase_index = 0
    last_pct_in_phase = 0.0
    overall_last = 0.0

    def emit(overall_pct: float, msg: str):
        nonlocal overall_last
        overall_pct = max(0.0, min(99.0, overall_pct))  # keep 100 for final "done"
        if overall_pct < overall_last:
            return  # keep monotonic overall
        overall_last = overall_pct

        elapsed = time.time() - start_time
        eta = int(elapsed * (100 - overall_pct) / overall_pct) if overall_pct > 1 else None

        if on_progress:
            on_progress(overall_pct, eta, msg)

    if on_progress:
        on_progress(0.0, None, "Preparing…")

    for raw in process.stdout:
        line = (raw or "").strip()

        # Mark "started" when demucs begins actual separation
        if not started:
            if "Separating track" in line:
                started = True
                if on_progress:
                    on_progress(1.0, None, "Separating audio…")
            else:
                continue  # ignore model download bars etc.

        # Parse progress percentage from demucs bar lines
        m = PROGRESS_RE.search(line)
        if not m:
            continue

        pct = float(m.group(1))
        pct = max(0.0, min(100.0, pct))

        # Detect phase transitions: if it drops a lot after being high, new bar started
        if last_pct_in_phase >= 90.0 and pct <= 10.0:
            phase_index = min(phases_total - 1, phase_index + 1)
            last_pct_in_phase = 0.0

        # Monotonic within the phase
        if pct < last_pct_in_phase:
            continue
        last_pct_in_phase = pct

        # Map to overall:
        # phase_index 0..3, pct 0..100 -> overall 0..100
        overall = ((phase_index + (pct / 100.0)) / phases_total) * 100.0

        emit(overall, "Separating audio…")

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("Demucs failed (see server logs)")

    vocals = list(out_dir.glob("**/vocals.mp3"))
    inst = list(out_dir.glob("**/no_vocals.mp3"))
    if not vocals or not inst:
        raise RuntimeError("Outputs not found after demucs run")

    vocals_path = max(vocals, key=lambda x: x.stat().st_mtime)
    inst_path = max(inst, key=lambda x: x.stat().st_mtime)

    shutil.copy(vocals_path, job_dir / "vocals_320.mp3")
    shutil.copy(inst_path, job_dir / "instrumental_320.mp3")

    if on_progress:
        on_progress(100.0, 0, "Done ✅")
