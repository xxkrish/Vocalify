const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type JobStartResponse = {
  jobId: string;
  statusUrl: string;
  vocalsUrl: string;
  instrumentalUrl: string;
};

export type JobStatus = {
  state: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  eta_seconds: number | null;
  message: string;
  error?: string | null;
};

export async function startSeparationJob(file: File): Promise<JobStartResponse> {
  const fd = new FormData();
  fd.append("file", file);

  const res = await fetch(`${API}/api/jobs`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());

  const data: JobStartResponse = await res.json();

  // convert relative URLs from backend into absolute URLs
  return {
    ...data,
    statusUrl: `${API}${data.statusUrl}`,
    vocalsUrl: `${API}${data.vocalsUrl}`,
    instrumentalUrl: `${API}${data.instrumentalUrl}`,
  };
}

export async function getJobStatus(statusUrl: string): Promise<JobStatus> {
  const res = await fetch(statusUrl);
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<JobStatus>;
}
