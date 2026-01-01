from __future__ import annotations

from pathlib import Path
from textual.screen import Screen
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static
from rich.console import Console
from rich.panel import Panel
from rich.image import Image


class GalleryScreen(Screen):
    '''
    Rich image gallery for generated outputs.
    Reads images from outputs/ directory (recursively).
    '''
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
    ]

    def compose(self):
        with Vertical():
            yield Static("Image Gallery", id="gallery-title")
            with ScrollableContainer(id="gallery-scroll"):
                yield Static("", id="gallery-content")

    def on_mount(self):
        self.load_images()

    def load_images(self):
        out = self.query_one("#gallery-content", Static)
        output_dir = Path("outputs")
        console = Console(record=True)

        if not output_dir.exists():
            out.update("No outputs/ directory found.")
            return

        images = list(output_dir.rglob("*.png")) + list(output_dir.rglob("*.jpg"))
        if not images:
            out.update("No images found in outputs/.")
            return

        for img_path in images[:20]:  # limit for safety
            try:
                console.print(Panel(Image.from_path(img_path), title=str(img_path)))
            except Exception as e:
                console.print(f"[red]Failed to load {img_path}: {e}[/red]")

        out.update(console.export_text())
