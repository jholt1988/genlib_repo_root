'use client';

import { useEffect, useState } from "react";
import { apiGet, API_BASE } from "../lib/api";

export default function GalleryPage() {
  const [path, setPath] = useState<string>("outputs");
  const [images, setImages] = useState<string[]>([]);
  const [err, setErr] = useState<string>("");

  async function load() {
    setErr("");
    try {
      const d: any = await apiGet(`/api/gallery?path=${encodeURIComponent(path)}`);
      setImages(d.images || []);
    } catch (e: any) {
      setErr(String(e?.message || e));
      setImages([]);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <h2>Gallery</h2>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input value={path} onChange={(e) => setPath(e.target.value)} style={{ width: 420, padding: 8 }} />
        <button onClick={load} style={{ padding: 10, fontWeight: 700 }}>Load</button>
        <div style={{ opacity: 0.8, fontSize: 12 }}>serving from backend: {API_BASE}</div>
      </div>
      {err ? <div style={{ color: "crimson", marginTop: 10 }}>{err}</div> : null}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {images.map((u) => (
          <a key={u} href={`${API_BASE}${u}`} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
            <img src={`${API_BASE}${u}`} style={{ width: "100%", borderRadius: 8, border: "1px solid #333" }} />
          </a>
        ))}
      </div>
    </div>
  );
}
