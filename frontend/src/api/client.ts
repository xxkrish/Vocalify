const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type JobStatus = {
  job_id: string;
  state: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  message: string;
  eta_seconds: number | null;
  error?: string | null;
};

export type JobMeta = {
  jobId: string;
  statusUrl: string;
  vocalsUrl: string;
  instrumentalUrl: string;
};

export async function startSeparationJob(file: File): Promise<JobMeta> {
  const fd = new FormData();
  fd.append("file", file);

  const res = await fetch(`${API}/api/jobs`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());

  const data = await res.json();

  return {
    jobId: data.jobId,
    statusUrl: `${API}${data.statusUrl}`,
    vocalsUrl: `${API}${data.vocalsUrl}`,
    instrumentalUrl: `${API}${data.instrumentalUrl}`,
  };
}

export async function getJobStatus(statusUrl: string): Promise<JobStatus> {
  const res = await fetch(statusUrl);
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as JobStatus;
}
