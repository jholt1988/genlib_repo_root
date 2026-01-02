from __future__ import annotations

import requests
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8000"


class BackendClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        r = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict | None = None) -> Any:
        r = requests.post(
            f"{self.base_url}{path}",
            json=payload or {},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    # ---- Jobs ----

    def list_jobs(self) -> list[dict]:
        return self._get("/jobs")["jobs"]

    def get_job(self, job_id: str) -> dict:
        return self._get(f"/jobs/{job_id}")

    def create_job(self, stack: str, engine: str = "forge") -> dict:
        return self._post("/jobs", {"stack": stack, "engine": engine})

    def cancel_job(self, job_id: str) -> dict:
        return self._post(f"/jobs/{job_id}/cancel")

    # ---- Outputs ----

    def job_outputs(self, job_id: str) -> dict:
        return self._get(f"/outputs/{job_id}")

    # ---- Stack runs ----

    def run_stack(
        self,
        stack: str,
        presets: list[str] | None = None,
        vars: dict | None = None,
        out: str | None = None,
        engine: str = "none",
        forge_dir: str | None = None,
    ) -> dict:
        payload = {
            "stack": stack,
            "presets": presets or [],
            "vars": vars or {},
            "out": out,
            "engine": engine,
            "forge_dir": forge_dir,
        }
        try:
            return self._post("/api/stacks/run", payload)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return self._post("/stacks/run", payload)
            raise

    def stream_job_logs(self, job_id: str):
        resp = requests.get(
            f"{self.base_url}/api/jobs/{job_id}/stream",
            stream=True,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.iter_lines(decode_unicode=True)
