from __future__ import annotations
import os, json, subprocess
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from job_queue import JobQueue
from typing_extensions import Sentinel

STACKS_DIR = Path(os.environ.get("GENLIB_STACKS_DIR","stacks")).expanduser().resolve()
OUTPUTS_ROOT = Path(os.environ.get("GENLIB_OUTPUTS_ROOT","outputs")).expanduser().resolve()

app = FastAPI(title="genlib-web", version="2.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_ROOT)), name="outputs")

queue = JobQueue()

class StackRun(BaseModel):
    stack: str
    vars: Dict[str, Any] = {}
    presets: List[str] = []
    out: str | None = None
    engine: str = "forge"
    forge_dir: str | None = None

class AgentRun(BaseModel):
    text: str
    planners: List[str] = ["rule","openai","ollama"]
    out: str | None = None
    engine: str = "forge"
    forge_dir: str | None = None

@app.post("/api/stacks/run")
def run_stack(req: StackRun):
    cmd = ["genlib","stack","run",req.stack]
    for p in req.presets:
        cmd += ["--preset",p]
    for k,v in req.vars.items():
        cmd += ["--var",f"{k}={v}"]
    if req.out:
        cmd += ["--out",req.out]
    cmd += ["--engine",req.engine]
    if req.engine=="forge":
        if not req.forge_dir:
            raise HTTPException(400,"forge_dir required")
        cmd += ["--forge-dir",req.forge_dir]
    jid = queue.submit({"type":"stack","stack":req.stack,"cmd":cmd,"out":req.out})
    return {"job_id":jid}

@app.post("/api/agent/run")
def run_agent(req: AgentRun):
    cmd = ["genlib","agent","run",req.text,"--planners",",".join(req.planners)]
    if req.out:
        cmd += ["--out",req.out]
    cmd += ["--engine",req.engine]
    if req.engine=="forge":
        if not req.forge_dir:
            raise HTTPException(400,"forge_dir required")
        cmd += ["--forge-dir",req.forge_dir]
    jid = queue.submit({"type":"agent","text":req.text,"cmd":cmd,"out":req.out})
    return {"job_id":jid}

@app.get("/api/jobs/{jid}")
def job(jid: str):
    j = queue.get(jid)
    if not j:
        raise HTTPException(404,"job not found")
    return j

@app.get("/api/gallery")
def gallery(path: str = Query("outputs")):
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(400,"invalid path")
    root = OUTPUTS_ROOT / rel.relative_to("outputs") if rel.parts and rel.parts[0]=="outputs" else OUTPUTS_ROOT/rel
    if not root.exists():
        return {"images":[]}
    imgs=[]
    for p in root.rglob("*"):
        if p.suffix.lower() in {".png",".jpg",".jpeg",".webp"}:
            imgs.append("/outputs/"+p.relative_to(OUTPUTS_ROOT).as_posix())
    return {"images":imgs}
