from __future__ import annotations

import os
from typing import Any

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from genlib.orchestrator import Orchestrator, OrchestrationError
from genlib.tui.services.backend_client import BackendClient


DEFAULT_PLANNERS = [
    p.strip()
    for p in os.environ.get("GENLIB_AGENT_PLANNERS", "rule").split(",")
    if p.strip()
]


if not DEFAULT_PLANNERS:
    DEFAULT_PLANNERS = ["rule"]

DEFAULT_STACKS_DIR = os.environ.get("GENLIB_AGENT_STACKS_DIR", "stacks")
DEFAULT_HYBRID_BACKEND = os.environ.get("GENLIB_AGENT_HYBRID_BACKEND", "openai")
DEFAULT_ENGINE = os.environ.get("GENLIB_AGENT_ENGINE", "none")


class AgentScreen(Screen):
    """Let users provide a natural-language goal and see the orchestrated plan."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("p", "plan_prompt", "Plan"),
        Binding("r", "run_plan", "Run plan"),
    ]

    def __init__(self):
        super().__init__()
        self._orchestrator = Orchestrator(
            DEFAULT_PLANNERS,
            stacks_dir=DEFAULT_STACKS_DIR,
            hybrid_backend=DEFAULT_HYBRID_BACKEND,
        )
        self._backend = BackendClient()
        self._selected_plan: dict[str, Any] | None = None

    def compose(self):
        with Vertical():
            yield Static("Agents", id="agent-title")
            yield Static(
                "Enter a natural-language goal, then hit 'Plan' (or Enter). "
                "The screen runs the orchestrator and shows the selected plan "
                "and candidate summaries inline.",
                id="agent-help",
            )
            yield Input(placeholder="e.g. render a cinematic portrait of a scientist", id="agent-text")
            yield Button("Plan", id="agent-plan")
            yield Static("", id="agent-result")
            yield Static("Run controls", id="agent-run-title")
            yield Input(placeholder="outputs/{stack}/{mood}", id="agent-out")
            yield Input(placeholder="engine (none or forge)", id="agent-engine")
            yield Input(placeholder="forge directory (when engine=forge)", id="agent-forge")
            yield Button("Run plan", id="agent-run")
            yield Static("", id="agent-run-status")

    def on_mount(self):
        self.query_one("#agent-text", Input).focus()
        self.query_one("#agent-result", Static).update("Ready when you are.")
        self.query_one("#agent-engine", Input).value = DEFAULT_ENGINE
        self.query_one("#agent-out", Input).value = ""
        self.query_one("#agent-forge", Input).value = ""
        self.query_one("#agent-run-status", Static).update("Run controls ready.")

    def action_plan_prompt(self):
        self._plan_current_text()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "agent-plan":
            self._plan_current_text()
        elif event.button.id == "agent-run":
            self.action_run_plan()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "agent-text":
            self._plan_current_text(event.value)

    def _plan_current_text(self, text: str | None = None):
        text = (text or self.query_one("#agent-text", Input).value or "").strip()
        result = self.query_one("#agent-result", Static)
        if not text:
            result.update("Please describe something to plan.")
            return

        result.update("Planning ...")
        try:
            trace = self._orchestrator.run(text)
        except OrchestrationError as exc:
            result.update(f"[red]Orchestration failed:[/red] {exc}")
            return
        except Exception as exc:  # pragma: no cover - best effort
            result.update(f"[red]Unexpected error:[/red] {exc}")
            return

        selected = trace.get("selected")
        if not selected:
            result.update("[red]No plan selected (validators rejected all candidates).[/red]")
            return

        self._selected_plan = selected
        self.query_one("#agent-out", Input).value = selected.get("out") or ""
        self.query_one("#agent-run-status", Static).update("Plan ready to run.")

        lines: list[str] = [
            f"[bold]Selected plan[/bold] (planner={selected.get('planner','?')}):",
            f"  Stack: {selected.get('stack')}",
            f"  Presets: {', '.join(selected.get('presets') or []) or '(none)'}",
            f"  Vars:",
        ]
        vars_dict = selected.get("vars") or {}
        if vars_dict:
            lines.extend(f"    {k} = {v}" for k, v in vars_dict.items())
        else:
            lines.append("    (none)")
        lines.extend(
            [
                f"  Count: {selected.get('count')}",
                f"  Constraints: {selected.get('constraints')}",
                f"  Outputs template: {selected.get('out') or '(none)'}",
            ]
        )

        lines.append("Candidates:")
        for cand in trace.get("candidates", []):
            suffix = " (selected)" if cand is selected else ""
            lines.append(f"  - {cand.get('planner','?')}: {cand.get('stack','?')}{suffix}")

        rejected = trace.get("rejected") or []
        if rejected:
            lines.append("Rejections:")
            for rej in rejected:
                planner = rej.get("planner") or "unknown"
                reason = rej.get("reason") or "(no reason)"
                lines.append(f"  - {planner}: {reason}")

        result.update("\n".join(lines))

    def action_run_plan(self):
        self._run_selected_plan()

    def _run_selected_plan(self):
        status = self.query_one("#agent-run-status", Static)
        if not self._selected_plan:
            status.update("Plan something before running.")
            return

        engine = (self.query_one("#agent-engine", Input).value or DEFAULT_ENGINE).strip() or DEFAULT_ENGINE
        out_value = self.query_one("#agent-out", Input).value.strip()
        out = out_value or self._selected_plan.get("out")
        forge_value = self.query_one("#agent-forge", Input).value.strip()
        forge_dir = forge_value or None

        status.update("Submitting job ...")
        try:
            job = self._backend.run_stack(
                stack=self._selected_plan["stack"],
                presets=list(self._selected_plan.get("presets") or []),
                vars=self._selected_plan.get("vars") or {},
                out=out or None,
                engine=engine,
                forge_dir=forge_dir,
            )
        except Exception as exc:  # pragma: no cover - best effort
            status.update(f"[red]Run failed:[/red] {exc}")
            return

        job_id = job.get("job_id") if isinstance(job, dict) else None
        status.update(f"Submitted job {job_id or '(unknown)'}")
