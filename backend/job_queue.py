from __future__ import annotations
import threading, queue, subprocess, time, uuid
from typing import Dict, Any

Job = Dict[str, Any]

class JobQueue:
    def __init__(self):
        self.q: queue.Queue[Job] = queue.Queue()
        self.jobs: Dict[str, Job] = {}
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
        self.q.put(job)
        return jid

    def get(self, jid: str) -> Job | None:
        return self.jobs.get(jid)

    def _worker(self):
        while True:
            job = self.q.get()
            job["status"] = "running"
            proc = subprocess.Popen(
                job["cmd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = proc.communicate()
            job["stdout"] = out
            job["stderr"] = err
            job["returncode"] = proc.returncode
            job["status"] = "completed" if proc.returncode == 0 else "failed"
            job["finished_ts"] = time.time()
            self.q.task_done()
