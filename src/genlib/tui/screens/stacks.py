from __future__ import annotations

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static


class StackScreen(Screen):
    """Placeholder view showing the prompt stack commands."""

    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
    ]

    def compose(self):
        with Vertical():
            yield Static("Stacks", id="stack-title")
            yield Static(
                "Create, resolve, and run prompt stacks with the "
                "`genlib stack` group (e.g., `genlib stack run <stack>`).",
                id="stack-body",
            )
