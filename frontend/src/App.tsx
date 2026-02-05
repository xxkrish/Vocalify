import { useEffect, useMemo, useRef, useState } from "react";
import { startSeparationJob, getJobStatus, type JobStatus } from "./api/client";

type Result = {
  jobId: string;
  vocalsUrl: string;
  instrumentalUrl: string;
};

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [job, setJob] = useState<JobStatus | null>(null);
  const pollRef = useRef<number | null>(null);

  // cleanup polling when page changes/unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  const label = useMemo(() => {
    if (!file) return "Drop audio here or click to upload (mp3, wav, m4a, flac)";
    return `${file.name} • ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  }, [file]);

  const onPick = (f: File | null) => {
    setFile(f);
    setResult(null);
    setError(null);
    setJob(null);
  };

  const fmtEta = (s: number | null) => {
    if (s == null) return "—";
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  };

  const stopPolling = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const onSeparate = async () => {
    if (!file) return;

    stopPolling();
    setBusy(true);
    setError(null);
    setResult(null);
    setJob(null);

    try {
      const meta = await startSeparationJob(file);

      // Start polling job status
      pollRef.current = window.setInterval(async () => {
        try {
          const status = await getJobStatus(meta.statusUrl);
          setJob(status);

          if (status.state === "done") {
            stopPolling();
            setBusy(false);

            setResult({
              jobId: meta.jobId,
              vocalsUrl: meta.vocalsUrl,
              instrumentalUrl: meta.instrumentalUrl,
            });
          }

          if (status.state === "error") {
            stopPolling();
            setBusy(false);
            setError(status.error ?? "Separation failed");
          }
        } catch {
          // ignore transient poll errors
        }
      }, 700);
    } catch (e: unknown) {
      setBusy(false);
      if (e instanceof Error) setError(e.message);
      else setError("Something went wrong");
    }
  };

  const onReset = () => {
    stopPolling();
    setBusy(false);
    setJob(null);
    onPick(null);
  };

  const progress = job ? Math.min(100, Math.max(0, job.progress)) : 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-zinc-900 text-zinc-100">
      <div className="mx-auto max-w-4xl px-6 py-14">
        <header className="flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <img src="/logo.jpg" alt="Vocalify logo" className="h-8 w-8" />
              <h1 className="text-3xl font-semibold tracking-tight leading-none">
                Vocalify
              </h1>
            </div>

            <p className="mt-2 text-zinc-400">
              Separate vocals and instrumental using Demucs. Output: 320kbps MP3.
            </p>
          </div>

          <span className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-xs text-zinc-300">
            Krish Patel
          </span>
        </header>

        <main className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-6 shadow-xl">
          <label className="block cursor-pointer rounded-2xl border border-dashed border-white/20 bg-black/20 px-6 py-10 text-center transition hover:border-white/40">
            <input
              type="file"
              className="hidden"
              accept=".mp3,.wav,.m4a,.flac"
              onChange={(e) => onPick(e.target.files?.[0] ?? null)}
            />
            <div className="text-sm text-zinc-200">{label}</div>
            <div className="mt-2 text-xs text-zinc-500">
              Tip: short clips process faster on CPU machines.
            </div>
          </label>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <button
              onClick={onSeparate}
              disabled={!file || busy}
              className="inline-flex items-center justify-center rounded-2xl bg-white px-5 py-3 text-sm font-medium text-zinc-900 transition disabled:opacity-50"
            >
              {busy ? "Separating..." : "Separate"}
            </button>

            <button
              onClick={onReset}
              className="inline-flex items-center justify-center rounded-2xl border border-white/15 bg-white/5 px-5 py-3 text-sm text-zinc-200 transition hover:bg-white/10"
            >
              Reset
            </button>
          </div>

          {/* Progress */}
          {job && job.state !== "done" && (
            <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm text-zinc-200">
                  {job.message || "Processing…"}
                </div>
                <div className="text-sm text-zinc-400 whitespace-nowrap">
                  {Math.round(progress)}% • ETA {fmtEta(job.eta_seconds)}
                </div>
              </div>

              <div className="mt-3 h-2 w-full rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-white transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <div className="mt-2 text-xs text-zinc-500">Stage: {job.stage}</div>
            </div>
          )}

          {error && (
            <div className="mt-5 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              {error}
            </div>
          )}

          {result && (
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <Card title="Vocals" url={result.vocalsUrl} />
              <Card title="Instrumental" url={result.instrumentalUrl} />
            </div>
          )}
        </main>

        <footer className="mt-8 text-xs text-zinc-500">
          React + FastAPI + Demucs • Built for portfolio
        </footer>
      </div>
    </div>
  );
}

function Card({ title, url }: { title: string; url: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/20 p-5">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{title}</div>
        <a
          className="text-xs text-zinc-300 underline underline-offset-4 hover:text-white"
          href={url}
          download
        >
          Download MP3
        </a>
      </div>
      <audio className="mt-4 w-full" controls src={url} />
      <div className="mt-3 text-xs text-zinc-500">320kbps</div>
    </div>
  );
}
