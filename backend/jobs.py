from fastapi import APIRouter, BackgroundTasks, HTTPException
from pathlib import Path
import subprocess, uuid, time, os, signal

from backend.db import create_job, update_job, get_job, list_jobs

router = APIRouter()
OUT = Path("outputs"); OUT.mkdir(exist_ok=True)

def _run(job_id, stack, engine, wd):
    update_job(job_id, status="running", started_at=time.time())
    with open(wd/"stdout.log","w") as o, open(wd/"stderr.log","w") as e:
        p = subprocess.Popen(["genlib","stack","run",stack,"--engine",engine], cwd=wd, stdout=o, stderr=e)
        update_job(job_id, pid=p.pid)
        rc = p.wait()
        update_job(job_id, status="completed" if rc==0 else "failed", exit_code=rc, finished_at=time.time())

@router.post("/")
def create(payload:dict, bg:BackgroundTasks):
    stack = payload.get("stack")
    if not stack: raise HTTPException(400,"Missing stack")
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    wd = OUT/job_id; wd.mkdir()
    create_job(job_id, stack, payload.get("engine","forge"), str(wd), str(wd/"stdout.log"), str(wd/"stderr.log"))
    bg.add_task(_run, job_id, stack, payload.get("engine","forge"), wd)
    
    meta = payload.get("meta")
    create_job_row(
        job_id=job_id,
        stack=stack,
        engine=engine,
        workdir=str(wd),
        stdout_log=str(wd/"stdout.log"),
        stderr_log=str(wd/"stderr.log"),
        meta_json=json.dumps(meta) if meta else None,
    
)return {"job_id":job_id,"status":"queued"}

@router.get("/")
def all(): return {"jobs": list_jobs()}

@router.get("/{job_id}")
def one(job_id:str):
    j=get_job(job_id)
    if not j: raise HTTPException(404,"Not found")
    return j

@router.post("/{job_id}/cancel")
def cancel(job_id:str):
    j=get_job(job_id)
    if not j: raise HTTPException(404,"Not found")
    pid=j.get("pid")
    if pid:
        try: os.kill(pid, signal.SIGTERM)
        except Exception: pass
    update_job(job_id, status="cancelled", cancelled_at=time.time(), finished_at=time.time())
    return {"job_id":job_id,"status":"cancelled"}
