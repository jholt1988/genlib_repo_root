from __future__ import annotations

from textual.screen import Screen
from textual.widgets import DataTable, Static
from textual.containers import Vertical
from textual.binding import Binding

from genlib.tui.services.backend_client import BackendClient
from genlib.tui.screens.job_detail import JobDetailScreen


class JobsScreen(Screen):
    BINDINGS = [
        Binding("enter", "open", "Open"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "cancel", "Cancel job"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    def __init__(self):
        super().__init__()
        self.client = BackendClient()
        self.jobs: list[dict] = []

    def compose(self):
        with Vertical():
            yield Static("Jobs", id="jobs-title")
            self.table = DataTable(id="jobs-table")
            self.table.add_columns(
                "job_id",
                "stack",
                "status",
                "engine",
                "created_at",
            )
            yield self.table

    def on_mount(self):
        self.load_jobs()

    def load_jobs(self):
        self.table.clear()
        self.jobs = self.client.list_jobs()
        for job in self.jobs:
            self.table.add_row(
                job["job_id"],
                job["stack"],
                job["status"],
                job["engine"],
                str(int(job["created_at"])),
            )

    def action_refresh(self):
        self.load_jobs()

    def action_cancel(self):
        if not self.table.cursor_row:
            return
        job_id = self.table.get_cell_at(self.table.cursor_row, 0)
        self.client.cancel_job(job_id)
        self.load_jobs()

    def action_open(self):
        if not self.table.cursor_row:
            return
        job_id = self.table.get_cell_at(self.table.cursor_row, 0)
        self.app.push_screen(JobDetailScreen(job_id))
