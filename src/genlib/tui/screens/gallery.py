from __future__ import annotations

from pathlib import Path

from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Static


class GalleryScreen(Screen):
    """Display generated images that live under an optional job directory."""

    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, job_id: str | None = None):
        super().__init__()
        self.job_id = job_id

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
        if self.job_id:
            output_dir /= self.job_id

        if not output_dir.exists():
            out.update("No outputs/ directory found.")
            return

        images = list(output_dir.rglob("*.png")) + list(output_dir.rglob("*.jpg"))
        if not images:
            out.update("No images found in outputs/.")
            return

        entries = [f"- {img_path}" for img_path in images[:20]]
        if len(images) > 20:
            entries.append(f"... and {len(images) - 20} more")
        out.update("\n".join(entries))
