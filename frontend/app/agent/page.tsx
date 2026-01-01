'use client';

import { useState } from "react";
import { apiPost } from "../lib/api";

export default function AgentPage() {
  const [text, setText] = useState<string>("cinematic portrait of a man 50mm, soft light");
  const [planners, setPlanners] = useState<string>("rule,openai,ollama");
  const [out, setOut] = useState<string>("outputs/{stack}/{mood}/{lens}");
  const [engine, setEngine] = useState<string>("forge");
  const [forgeDir, setForgeDir] = useState<string>("");
  const [log, setLog] = useState<string>("");

  async function runAgent() {
    setLog("Running…");
    try {
      const res: any = await apiPost("/api/agent/run", {
        text,
        planners: planners.split(",").map(s => s.trim()).filter(Boolean),
        out,
        engine,
        forge_dir: forgeDir || null,
        explain: true,
        dry_run: false
      });
      setLog((res.stdout || "") + "\n" + (res.stderr || ""));
    } catch (e: any) {
      setLog(String(e?.message || e));
    }
  }

  return (
    <div style={{ maxWidth: 900, display: "grid", gap: 10 }}>
      <h2>Agent Console</h2>

      <label>
        Prompt
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} style={{ width: "100%", padding: 10 }} />
      </label>

      <label>
        Planners (comma list)
        <input value={planners} onChange={(e) => setPlanners(e.target.value)} style={{ width: "100%", padding: 8 }} />
      </label>

      <label>
        Out template
        <input value={out} onChange={(e) => setOut(e.target.value)} style={{ width: "100%", padding: 8 }} />
      </label>

      <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: 10 }}>
        <label>
          Engine
          <select value={engine} onChange={(e) => setEngine(e.target.value)} style={{ width: "100%", padding: 8 }}>
            <option value="forge">forge</option>
            <option value="none">none</option>
          </select>
        </label>
        <label>
          Forge dir
          <input value={forgeDir} onChange={(e) => setForgeDir(e.target.value)} placeholder="/home/jholt/stable-diffusion-webui-forge" style={{ width: "100%", padding: 8 }} />
        </label>
      </div>

      <button onClick={runAgent} style={{ padding: 10, fontWeight: 700 }}>Run Agent</button>

      <pre style={{ whiteSpace: "pre-wrap", background: "#0b0b0b", color: "#ddd", padding: 12, borderRadius: 8 }}>
        {log}
      </pre>
    </div>
  );
}
