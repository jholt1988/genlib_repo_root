from __future__ import annotations

import queue
import subprocess
import threading
import time
import uuid
from typing import Dict, Any, Generator

Job = Dict[str, Any]


class JobQueue:
    def __init__(self):
        self.q: "queue.Queue[Job]" = queue.Queue()
        self.jobs: Dict[str, Job] = {}
        self.logs: Dict[str, queue.Queue[str]] = {}
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def submit(self, job: Job) -> str:
        jid = uuid.uuid4().hex[:12]
        job["id"] = jid
        job["status"] = "queued"
        job["stdout"] = ""
        job["stderr"] = ""
        job["created_ts"] = time.time()
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
        # drain remaining items
        while not log_queue.empty():
            yield log_queue.get()

    def _worker(self):
        while True:
            job = self.q.get()
            jid = job["id"]
            job["status"] = "running"
            self._log(jid, "Job started")
            proc = subprocess.Popen(
                job["cmd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )

            for stream_name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
                if stream is None:
                    continue
                threading.Thread(
                    target=self._tail_stream,
                    args=(jid, stream_name, stream),
                    daemon=True,
                ).start()

            return_code = proc.wait()
            job["returncode"] = return_code
            job["status"] = "completed" if return_code == 0 else "failed"
            job["finished_ts"] = time.time()
            self._log(jid, f"Job finished ({job['status']})")
            self.q.task_done()

    def _tail_stream(self, jid: str, name: str, stream):
        assert jid in self.jobs
        for line in stream:
            clean = line.rstrip("\n")
            key = f"{name}:{clean}"
            self.logs[jid].put(key)
            if name == "stdout":
                self.jobs[jid]["stdout"] += clean + "\n"
            else:
                self.jobs[jid]["stderr"] += clean + "\n"
        stream.close()

    def _log(self, jid: str, message: str):
        prefix = f"info:{message}"
        self.logs[jid].put(prefix)
