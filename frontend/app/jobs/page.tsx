'use client';

import { useEffect, useState } from "react";
import { backend } from "../lib/api";

type Job = any;


export default async function JobsPage() {
  const { jobs } = await backend.jobs();
 
  const [err, setErr] = useState<string>("");

  

  return (
    <div style={{ maxWidth: 1100 }}>
      <h2>Jobs</h2>
      {err ? <div style={{ color: "crimson" }}>{err}</div> : null}
      <div style={{ display: "grid", gap: 10 }}>
        {jobs.map((j, i) => (
          <div key={i} style={{ border: "1px solid #333", borderRadius: 8, padding: 10 }}>
            <div style={{ fontWeight: 700 }}>
              {j.type || "job"} • {j.stack || j.text || "—"} • {j.ok ? "✅" : "❌"}
            </div>
            <div style={{ fontSize: 12, opacity: 0.85 }}>out: {j.out || "—"}</div>
            <div style={{ fontSize: 12, opacity: 0.85 }}>engine: {j.engine || "—"}</div>
            <details>
              <summary>command</summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(j.cmd, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
