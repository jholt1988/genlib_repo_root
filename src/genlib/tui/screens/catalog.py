from __future__ import annotations

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static


class CatalogScreen(Screen):
    """Placeholder view that points to the catalog CLI features."""

    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
    ]

    def compose(self):
        with Vertical():
            yield Static("Catalog", id="catalog-title")
            yield Static(
                "This view is a stub for catalog exploration. Use "
                "`genlib catalog search` or `genlib catalog show <ref>` "
                "from the CLI for detailed catalog data.",
                id="catalog-body",
            )
