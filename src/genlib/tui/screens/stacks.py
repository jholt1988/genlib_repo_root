from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from genlib.tui.services.backend_client import BackendClient

DEFAULT_STACKS_DIR = os.environ.get("GENLIB_STACKS_DIR", "stacks")


class StackScreen(Screen):
    """List available stacks and submit them to the backend queue."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("f", "focus_filter", "Filter"),
    ]

    def __init__(self):
        super().__init__()
        self._stacks_dir = Path(DEFAULT_STACKS_DIR).expanduser()
        self._stacks: List[Dict[str, Any]] = []
        self._row_map: Dict[Any, Dict[str, Any]] = {}
        self._selected_stack: Dict[str, Any] | None = None
        self._backend = BackendClient()

    def compose(self):
        with Horizontal():
            with Vertical(id="stack-browser"):
                yield Static("Stacks", id="stack-title")
                yield Input(placeholder="Filter stack name", id="stack-filter")
                self.table = DataTable(id="stack-table")
                self.table.add_columns("Stack", "Intent", "Presets", "Updated")
                self.table.cursor_type = "row"
                yield self.table
                yield Static("", id="stack-status")
            with Vertical(id="stack-detail-pane"):
                yield Static("Stack details", id="stack-detail-title")
                with ScrollableContainer(id="stack-detail-scroll"):
                    yield Static("Select a stack to inspect it.", id="stack-detail")
                yield Static("Run controls", id="stack-run-title")
                yield Input(placeholder="presets (comma-separated)", id="stack-presets")
                yield Input(placeholder="vars (k=v, ...)", id="stack-vars")
                yield Input(placeholder="outputs template (e.g. outputs/{stack})", id="stack-out")
                yield Button("Run stack", id="stack-run")
                yield Static("", id="stack-run-status")

    def on_mount(self):
        self.query_one("#stack-filter", Input).focus()
        self._load_stacks()

    def action_focus_filter(self):
        self.query_one("#stack-filter", Input).focus()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "stack-filter":
            self._populate_table(event.value)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        stack = self._row_map.get(event.row_key)
        if stack:
            self._selected_stack = stack
            self._update_detail(stack)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stack-run":
            self._run_selected_stack()

    def _load_stacks(self):
        self._stacks.clear()
        if not self._stacks_dir.exists():
            self._stacks_dir.mkdir(parents=True, exist_ok=True)
        for p in sorted(self._stacks_dir.glob("*.json")):
            try:
                doc = p.read_text(encoding="utf-8")
                parsed = json.loads(doc)
            except Exception:
                continue
            self._stacks.append(
                {
                    "name": p.stem,
                    "path": p,
                    "doc": parsed,
                    "mtime": p.stat().st_mtime,
                }
            )
        self._populate_table()

    def _populate_table(self, query: str | None = None):
        self.table.clear()
        self._row_map.clear()
        needle = (query or "").strip().lower()
        first_key: Any | None = None
        for stack in self._stacks:
            name = stack["name"]
            if needle and needle not in name.lower():
                continue
            doc = stack["doc"] or {}
            presets = ", ".join(doc.get("presets") or [])
            row_key = self.table.add_row(
                name,
                doc.get("intent") or "",
                presets,
                time.strftime("%Y-%m-%d %H:%M", time.localtime(stack["mtime"])),
            )
            self._row_map[row_key] = stack
            if first_key is None:
                first_key = row_key
        status = self.query_one("#stack-status", Static)
        status.update(f"{len(self._row_map)} stacks available (filter: {needle or 'none'})")
        if first_key:
            stack = self._row_map[first_key]
            self._selected_stack = stack
            self._update_detail(stack)
        else:
            self._selected_stack = None
            self.query_one("#stack-detail", Static).update("No stack selected.")

    def _update_detail(self, stack: Dict[str, Any]):
        doc = stack["doc"] or {}
        detail = self.query_one("#stack-detail", Static)
        lines = [
            f"Stack: {stack['name']}",
            f"Intent: {doc.get('intent') or 'unknown'}",
            f"Presets: {', '.join(doc.get('presets') or []) or '(none)'}",
            f"Vars: {', '.join(doc.get('vars') or {}) or '(none)'}",
            f"File: {stack['path']}",
        ]
        detail.update("\n".join(lines))

    def _parse_presets(self, value: str) -> List[str]:
        return [p.strip() for p in value.split(",") if p.strip()]

    def _parse_vars(self, value: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for part in value.split(","):
            if "=" not in part:
                continue
            name, val = part.split("=", 1)
            out[name.strip()] = val.strip()
        return out

    def _run_selected_stack(self):
        status = self.query_one("#stack-run-status", Static)
        if not self._selected_stack:
            status.update("Select a stack to run.")
            return
        presets = self._parse_presets(self.query_one("#stack-presets", Input).value or "")
        vars_input = self._parse_vars(self.query_one("#stack-vars", Input).value or "")
        out_value = self.query_one("#stack-out", Input).value.strip()
        status.update("Submitting job...")
        try:
            job = self._backend.run_stack(
                stack=self._selected_stack["name"],
                presets=presets,
                vars=vars_input,
                out=out_value or None,
                engine="forge",
            )
        except Exception as exc:
            status.update(f"[red]Run failed:[/red] {exc}")
            return
        job_id = job.get("job_id") if isinstance(job, dict) else None
        status.update(f"Submitted job {job_id or '(unknown)'}")
