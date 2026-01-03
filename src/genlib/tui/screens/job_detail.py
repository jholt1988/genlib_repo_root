from __future__ import annotations

import json
import threading
from typing import Any

from textual.screen import Screen
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static

from genlib.tui.services.backend_client import BackendClient
from genlib.tui.screens.gallery import GalleryScreen


class JobDetailScreen(Screen):
    BINDINGS = [
        ("g", "gallery", "View Gallery"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.client = BackendClient()
        self._stream_stop = threading.Event()
        self._stream_thread: threading.Thread | None = None
        self._log_cache: list[str] = []

    def compose(self):
        with Vertical():
            yield Static(f"Job: {self.job_id}", id="job-title")
            with ScrollableContainer():
                yield Static("", id="job-body")

    def on_mount(self):
        job = self.client.get_job(self.job_id)
        meta = job.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {"raw": meta}

        def format_ts(key: str) -> str:
            val = job.get(key)
            return str(val) if val is not None else "n/a"

        lines = [
            f"Status: {job.get('status','?')}",
            f"Stack: {job.get('stack','?')}",
            f"Engine: {job.get('engine','?')}",
            f"Created: {format_ts('created_ts')}",
            f"Started: {format_ts('started_ts')}",
            f"Finished: {format_ts('finished_ts')}",
            "",
            "Outputs:",
            "\n".join(job.get("outputs") or []) or "(none)",
            "",
            "Metadata:",
            json.dumps(meta, indent=2) if meta else "(none)",
            "",
            "Stdout:",
            (job.get("stdout") or "(none)").strip(),
            "",
            "Stderr:",
            (job.get("stderr") or "(none)").strip(),
        ]
        self.query_one("#job-body", Static).update("\n".join(lines))
        self._start_stream()

    def on_unmount(self):
        self._stream_stop.set()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=0.1)

    def action_gallery(self):
        self.app.push_screen(GalleryScreen(self.job_id))

    def _start_stream(self):
        if self._stream_thread and self._stream_thread.is_alive():
            return

        def run():
            try:
                for raw in self.client.stream_job_logs(self.job_id):
                    if self._stream_stop.is_set():
                        break
                    if not raw.startswith("data:"):
                        continue
                    payload = raw.split("data:", 1)[1].strip()
                    if not payload:
                        continue
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        event = {"message": payload}
                    self.call_from_thread(self._handle_stream_event, event)
            except Exception as exc:
                self.call_from_thread(
                    self._handle_stream_event,
                    {"channel": "error", "message": str(exc)},
                )

        self._stream_thread = threading.Thread(target=run, daemon=True)
        self._stream_thread.start()

    def _handle_stream_event(self, event: dict[str, Any]):
        channel = event.get("channel", "info")
        message = event.get("message", "")
        log_line = f"[{channel}] {message}"
        self._log_cache.append(log_line)
        body = self.query_one("#job-body", Static)
        body.update(f"{body.renderable}\n{log_line}")
