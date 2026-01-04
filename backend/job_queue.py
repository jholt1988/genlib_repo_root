from __future__ import annotations

import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator

from genlib.catalog.utils import ensure_catalog
from genlib.compose import compose_from_stack
from genlib.engines.forge_api import (
    DEFAULT_FORGE_API_URL,
    build_txt2img_payload,
    invoke_txt2img,
    save_images,
)
from genlib.stack.run import resolve_stack_document
from genlib.utils import DEFAULT_FORGE_MODELS_DIR, env_default

Job = Dict[str, Any]

DEFAULT_STACKS_DIR = os.environ.get("GENLIB_STACKS_DIR", "stacks")
DEFAULT_MODELS_ROOT = env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR)
DEFAULT_CATALOG_PATH = os.environ.get("GENLIB_CATALOG_PATH")
DEFAULT_FORGE_URL = os.environ.get("FORGE_API_URL", DEFAULT_FORGE_API_URL)


class JobQueue:
    def __init__(self, outputs_root: Path, forge_url: str | None = None):
        self.q: "queue.Queue[Job]" = queue.Queue()
        self.jobs: Dict[str, Job] = {}
        self.logs: Dict[str, queue.Queue[str]] = {}
        self.outputs_root = outputs_root
        self.forge_api_url = forge_url or DEFAULT_FORGE_URL
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def submit(self, job: Job) -> str:
        jid = uuid.uuid4().hex[:12]
        job["job_id"] = jid
        job["status"] = "queued"
        job["stdout"] = ""
        job["stderr"] = ""
        job["created_ts"] = time.time()
        job.setdefault("outputs", [])
        job.setdefault("presets", [])
        job.setdefault("vars", {})
        job.setdefault("count", 1)
        job["cancel_requested"] = False
        self.jobs[jid] = job
        self.logs[jid] = queue.Queue()
        self.q.put(job)
        return jid

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def stream(self, jid: str) -> Generator[str, None, None]:
        if jid not in self.jobs:
            return
        log_queue = self.logs.setdefault(jid, queue.Queue())
        while True:
            try:
                line = log_queue.get(timeout=0.5)
            except queue.Empty:
                status = self.jobs.get(jid, {}).get("status")
                if status not in ("running", "queued"):
                    break
                continue
            yield line
            log_queue.task_done()
        while not log_queue.empty():
            yield log_queue.get()

    def cancel(self, jid: str) -> bool:
        job = self.jobs.get(jid)
        if not job:
            return False
        job["cancel_requested"] = True
        if job.get("status") == "queued":
            job["status"] = "cancelled"
            job["finished_ts"] = time.time()
            self._log(jid, "Job cancelled before execution")
        else:
            self._log(jid, "Cancel requested")
        return True

    def _worker(self):
        while True:
            job = self.q.get()
            jid = job["job_id"]
            if job.get("cancel_requested"):
                job["status"] = "cancelled"
                job["finished_ts"] = time.time()
                self._log(jid, "Job cancelled before execution")
                self.q.task_done()
                continue

            job["status"] = "running"
            job["started_ts"] = time.time()
            self._log(jid, "Job started")
            try:
                if job.get("type") == "stack":
                    self._execute_stack_job(jid, job)
                else:
                    raise RuntimeError(f"unsupported job type: {job.get('type')}")
            except Exception as exc:
                job["status"] = "failed"
                job["stderr"] += f"{exc}\n"
                job["returncode"] = 1
                job["finished_ts"] = time.time()
                self._log(jid, f"Job failed: {exc}")
            finally:
                self.q.task_done()

    def _execute_stack_job(self, jid: str, job: Job):
        resolved_doc = resolve_stack_document(
            job.get("stack"),
            stacks_dir=job.get("stacks_dir") or DEFAULT_STACKS_DIR,
            presets=job.get("presets"),
            vars=job.get("vars"),
        )
        models_root = Path(job.get("models_root") or DEFAULT_MODELS_ROOT).expanduser().resolve()
        catalog_path = job.get("catalog_path") or DEFAULT_CATALOG_PATH
        catalog_file, created = ensure_catalog(models_root, catalog_path)
        if created:
            self._log(jid, f"Catalog built at {catalog_file}")
        self._log(jid, f"Composing stack {resolved_doc.get('name')}")
        result = compose_from_stack(
            resolved_doc,
            models_root=str(models_root),
            catalog_path=str(catalog_file),
            explain=False,
        )
        payload = build_txt2img_payload(
            result,
            count=max(1, int(job.get("count") or 1)),
            seed=job.get("seed"),
        )
        self._log(jid, f"Calling AUTOMATIC1111 API ({self.forge_api_url})")
        data = invoke_txt2img(self.forge_api_url, payload)
        images = data.get("images") or []
        saved = save_images(images, self.outputs_root / jid)
        job["outputs"] = [str(p) for p in saved]
        job["meta"] = {
            "prompt": payload.get("prompt"),
            "negative_prompt": payload.get("negative_prompt"),
            "params": payload,
            "api_info": data.get("info"),
        }
        job["stdout"] += f"Saved {len(saved)} image(s)\n"
        job["returncode"] = 0
        job["status"] = "completed"
        job["finished_ts"] = time.time()
        self._log(jid, "Job completed")

    def _log(self, jid: str, message: str):
        if jid not in self.logs:
            self.logs[jid] = queue.Queue()
        prefix = f"info:{message}"
        self.logs[jid].put(prefix)
