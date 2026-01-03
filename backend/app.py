from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from job_queue import JobQueue
OUTPUTS_ROOT = Path(os.environ.get("GENLIB_OUTPUTS_ROOT", "outputs")).expanduser().resolve()

app = FastAPI(title="genlib-web", version="2.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_ROOT)), name="outputs")

queue = JobQueue(outputs_root=OUTPUTS_ROOT)


class StackRun(BaseModel):
    stack: str
    vars: Dict[str, Any] = {}
    presets: List[str] = []
    out: str | None = None
    engine: str = "forge"
    forge_dir: str | None = None
    seed: int | None = None
    stacks_dir: str | None = None
    models_root: str | None = None
    catalog_path: str | None = None
    count: int | None = None


class AgentRun(BaseModel):
    text: str
    planners: List[str] = ["rule", "openai", "ollama"]
    out: str | None = None
    engine: str = "forge"
    forge_dir: str | None = None


@app.post("/api/stacks/run")
def run_stack(req: StackRun):
    job_data: Dict[str, Any] = {
        "type": "stack",
        "stack": req.stack,
        "presets": req.presets,
        "vars": req.vars,
        "out": req.out,
        "engine": req.engine,
        "forge_dir": req.forge_dir,
        "seed": req.seed,
    }
    if req.count is not None:
        job_data["count"] = req.count
    if req.stacks_dir:
        job_data["stacks_dir"] = req.stacks_dir
    if req.models_root:
        job_data["models_root"] = req.models_root
    if req.catalog_path:
        job_data["catalog_path"] = req.catalog_path
    jid = queue.submit(job_data)
    return {"job_id": jid}


@app.post("/api/agent/run")
def run_agent(req: AgentRun):
    raise HTTPException(501, "agent endpoint is not supported by this backend")


@app.get("/api/jobs")
def list_jobs():
    jobs = sorted(queue.jobs.values(), key=lambda j: j.get("created_ts", 0), reverse=True)
    return {"jobs": jobs}


@app.get("/api/jobs/{jid}")
def job(jid: str):
    j = queue.get(jid)
    if not j:
        raise HTTPException(404, "job not found")
    return j


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    if not queue.cancel(jid):
        raise HTTPException(404, "job not found")
    return {"job_id": jid, "status": "cancelled"}


@app.get("/api/gallery")
def gallery(path: str = Query("outputs")):
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(400, "invalid path")
    root = (
        OUTPUTS_ROOT / rel.relative_to("outputs")
        if rel.parts and rel.parts[0] == "outputs"
        else OUTPUTS_ROOT / rel
    )
    if not root.exists():
        return {"images": []}
    imgs = []
    for p in root.rglob("*"):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            imgs.append("/outputs/" + p.relative_to(OUTPUTS_ROOT).as_posix())
    return {"images": imgs}


@app.get("/api/jobs/{jid}/stream")
def stream_job(jid: str):
    job = queue.get(jid)
    if not job:
        raise HTTPException(404, "job not found")

    def event_stream():
        for raw in queue.stream(jid):
            if not raw:
                continue
            channel, _, payload = raw.partition(":")
            payload = payload or ""
            event = {
                "job_id": jid,
                "channel": channel,
                "message": payload,
                "status": job.get("status"),
            }
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
