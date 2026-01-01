from __future__ import annotations

import json
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

        lines = [
            f"Status: {job['status']}",
            f"Stack: {job['stack']}",
            f"Engine: {job['engine']}",
            "",
            "Metadata:",
            json.dumps(meta, indent=2) if meta else "(none)",
            "",
            f"Workdir: {job['workdir']}",
            f"Stdout: {job['stdout_log']}",
            f"Stderr: {job['stderr_log']}",
        ]
        self.query_one("#job-body", Static).update("\n".join(lines))

    def action_gallery(self):
        self.app.push_screen(GalleryScreen(self.job_id))
