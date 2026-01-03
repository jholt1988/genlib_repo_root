from __future__ import annotations

import base64
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator

import requests

from genlib.catalog.index import build_catalog
from genlib.presets import load_presets, PresetError
from genlib.stack.cli import resolve_stack
from genlib.stack.schema import validate_stack
from genlib.utils import DEFAULT_FORGE_MODELS_DIR, dump_json, env_default
from genlib.vars import resolve_vars, VarError

Job = Dict[str, Any]

DEFAULT_STACKS_DIR = os.environ.get("GENLIB_STACKS_DIR", "stacks")
DEFAULT_MODELS_ROOT = env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR)
DEFAULT_CATALOG_PATH = os.environ.get("GENLIB_CATALOG_PATH")
DEFAULT_FORGE_API_URL = os.environ.get("FORGE_API_URL", "http://127.0.0.1:7860")


class JobQueue:
    def __init__(self, outputs_root: Path, forge_url: str | None = None):
        self.q: "queue.Queue[Job]" = queue.Queue()
        self.jobs: Dict[str, Job] = {}
        self.logs: Dict[str, queue.Queue[str]] = {}
        self.outputs_root = outputs_root
        self.forge_api_url = forge_url or DEFAULT_FORGE_API_URL
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
        try:
            resolved_doc = self._resolve_stack_document(job)
            models_root = Path(job.get("models_root") or DEFAULT_MODELS_ROOT).expanduser().resolve()
            catalog_path = job.get("catalog_path") or DEFAULT_CATALOG_PATH
            catalog_file = self._resolve_catalog_file(jid, models_root, catalog_path)
            result = compose_from_stack(
                resolved_doc,
                models_root=str(models_root),
                catalog_path=str(catalog_file) if catalog_file else None,
                explain=False,
            )
            payload = self._build_txt2img_payload(job, result)
            self._log(jid, f"Calling AUTOMATIC1111 API ({self.forge_api_url})")
            resp = requests.post(
                f"{self.forge_api_url.rstrip('/')}/sdapi/v1/txt2img",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            images = data.get("images") or []
            saved = self._save_images(jid, images)
            job["outputs"] = saved
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
        except Exception as exc:
            self._log(jid, f"Execution failed: {exc}")
            raise

    def _resolve_stack_document(self, job: Job) -> Dict[str, Any]:
        stacks_dir = job.get("stacks_dir") or DEFAULT_STACKS_DIR
        stacks_path = Path(stacks_dir).expanduser().resolve()
        stack_name = job.get("stack")
        if not stack_name:
            raise RuntimeError("stack missing in job data")
        doc, _ = resolve_stack(stacks_path, stack_name)
        errs = validate_stack(doc)
        if errs:
            raise RuntimeError("stack invalid: " + "; ".join(errs))

        values: Dict[str, Any] = {}
        for preset in job.get("presets") or []:
            try:
                values.update(load_presets(doc, preset))
            except PresetError as exc:
                raise RuntimeError(f"preset '{preset}' invalid: {exc}") from exc

        vars_block = job.get("vars") or {}
        if not isinstance(vars_block, dict):
            raise RuntimeError("vars must be an object")
        values.update(vars_block)

        try:
            docs, _ = resolve_vars(doc, values)
        except VarError as exc:
            raise RuntimeError(f"vars invalid: {exc}") from exc

        return docs[0]

    def _resolve_catalog_file(self, jid: str, models_root: Path, catalog_path: str | None) -> Path | None:
        models_root.mkdir(parents=True, exist_ok=True)
        if catalog_path:
            path = Path(catalog_path).expanduser()
        else:
            path = models_root / "catalog.json"
        if not path.exists():
            self._log(jid, f"Building catalog at {path}")
            catalog = build_catalog(models_root, include_hash=False, validate=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            dump_json(path, catalog)
            self._log(jid, "Catalog build complete")
        return path

    def _build_txt2img_payload(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        params = result.get("params") or {}
        steps = int(params.get("steps", 28))
        cfg_scale = float(params.get("cfg_scale", params.get("cfg", 7.0)))
        sampler = params.get("sampler") or params.get("sampler_name") or "Euler a"
        width = int(params.get("width", 512))
        height = int(params.get("height", 512))
        count = max(1, int(job.get("count") or 1))
        lora_tokens = " ".join(
            f"<lora:{l['forge_id']}:{l['weight']}>" for l in (result.get("loras") or []) if l.get("forge_id")
        )
        positive = result.get("positive_prompt", "")
        prompt = f"{lora_tokens} {positive}".strip() if positive or lora_tokens else ""

        payload = {
            "prompt": prompt,
            "negative_prompt": result.get("negative_prompt", ""),
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler,
            "width": width,
            "height": height,
            "seed": job.get("seed"),
            "n_iter": count,
            "batch_size": 1,
        }
        return {k: v for k, v in payload.items() if v not in (None, "")}

    def _save_images(self, jid: str, images: list[str]) -> list[str]:
        saved = []
        out_dir = self.outputs_root / jid
        out_dir.mkdir(parents=True, exist_ok=True)
        for idx, encoded in enumerate(images, start=1):
            payload = encoded.split(",", 1)[1] if "," in encoded else encoded
            data = base64.b64decode(payload)
            target = out_dir / f"image_{idx:02d}.png"
            target.write_bytes(data)
        saved.append(str(target))
            self._log(jid, f"Image saved: {target}")
        return saved

    def _log(self, jid: str, message: str):
        if jid not in self.logs:
            self.logs[jid] = queue.Queue()
        prefix = f"info:{message}"
        self.logs[jid].put(prefix)
