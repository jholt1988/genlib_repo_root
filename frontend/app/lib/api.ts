import { get } from "node:http";

export const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function api<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const backend = {
  health: () => api("/health"),
  catalog: () => api("/catalog"),
  stacks: () => api("/stacks"),
  jobs: () => api<{ jobs: any[] }>("/jobs"),
  job: (id: string) => api(`/jobs/${id}`),
  createJob: (stack: string, engine = "forge", meta?: any) =>
    api("/jobs", {
      method: "POST",
      body: JSON.stringify({ stack, engine, meta }),
    }),
  cancelJob: (id: string) =>
    api(`/jobs/${id}/cancel`, { method: "POST" }),
  outputs: (jobId: string) => api(`/outputs/${jobId}`),
  agentPlan: (prompt: string, planner = "rule") =>
    api("/agent/plan", {
      method: "POST",
      body: JSON.stringify({ prompt, planner }),
    }),
  agentRun: (params: any) =>
    api("/agent/plans", {
      method: "POST",
      body: JSON.stringify(params),
    }),
    gallery: (path: string) =>
     api(`/gallery?path=${encodeURIComponent(path)}`),
    runStack: (stack: string, engine = "forge", meta?: any) =>
     api("/stacks/run", {
      method: "POST",
      body: JSON.stringify({ stack, engine, meta }),
    }),

};
