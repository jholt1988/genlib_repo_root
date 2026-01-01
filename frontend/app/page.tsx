'use client';

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "./lib/api";

type StackItem = {
  name: string;
  intent?: string;
  extends?: string;
  vars: string[];
  presets: string[];
  path: string;
};

export default function StacksPage() {
  const [stacks, setStacks] = useState<StackItem[]>([]);
  const [selected, setSelected] = useState<StackItem | null>(null);
  const [vars, setVars] = useState<string>("");
  const [presets, setPresets] = useState<string>("");
  const [out, setOut] = useState<string>("outputs/{stack}/{mood}/{lens}");
  const [engine, setEngine] = useState<string>("forge");
  const [forgeDir, setForgeDir] = useState<string>("");
  const [log, setLog] = useState<string>("");

  useEffect(() => {
    apiGet<{ stacks: StackItem[] }>("/api/stacks").then((d) => setStacks(d.stacks));
  }, []);

  async function runStack() {
    if (!selected) return;
    const varsObj: any = {};
    vars.split(",").map(s => s.trim()).filter(Boolean).forEach(part => {
      const [k, ...rest] = part.split("=");
      if (!k || rest.length === 0) return;
      varsObj[k.trim()] = rest.join("=").trim();
    });

    const payload: any = {
      stack: selected.name,
      vars: varsObj,
      presets: presets.split(",").map(s => s.trim()).filter(Boolean),
      out,
      engine,
      forge_dir: forgeDir || null,
      explain: true
    };

    setLog("Running…");
    try {
      const res: any = await apiPost("/api/stacks/run", payload);
      setLog((res.stdout || "") + "\n" + (res.stderr || ""));
    } catch (e: any) {
      setLog(String(e?.message || e));
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 16 }}>
      <div>
        <h2>Stacks</h2>
        <div style={{ border: "1px solid #333", borderRadius: 8, overflow: "hidden" }}>
          {stacks.map((s) => (
            <div
              key={s.name}
              onClick={() => setSelected(s)}
              style={{
                padding: 10,
                cursor: "pointer",
                borderBottom: "1px solid #222",
                background: selected?.name === s.name ? "#111" : "transparent",
                color: "#ddd"
              }}
            >
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div style={{ fontSize: 12, opacity: 0.8 }}>
                {s.intent || "—"} • vars: {s.vars.length} • presets: {s.presets.length}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2>Run</h2>
        {selected ? (
          <div style={{ display: "grid", gap: 10, maxWidth: 900 }}>
            <div style={{ color: "#bbb" }}>
              <b>{selected.name}</b> — {selected.intent || "no intent"}
              <div style={{ fontSize: 12, opacity: 0.8 }}>file: {selected.path}</div>
            </div>

            <label>
              Vars (key=value,key2=value2)
              <input value={vars} onChange={(e) => setVars(e.target.value)} style={{ width: "100%", padding: 8 }} />
            </label>

            <label>
              Presets (p1,p2)
              <input value={presets} onChange={(e) => setPresets(e.target.value)} style={{ width: "100%", padding: 8 }} />
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

            <button onClick={runStack} style={{ padding: 10, fontWeight: 700 }}>Run Stack</button>

            <pre style={{ whiteSpace: "pre-wrap", background: "#0b0b0b", color: "#ddd", padding: 12, borderRadius: 8 }}>
              {log}
            </pre>
          </div>
        ) : (
          <div style={{ color: "#888" }}>Select a stack to run.</div>
        )}
      </div>
    </div>
  );
}
