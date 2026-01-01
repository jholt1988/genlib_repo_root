from __future__ import annotations

from textual.app import App
from textual.widgets import Header, Footer

from genlib.tui.screens.catalog import CatalogScreen
from genlib.tui.screens.stacks import StackScreen
from genlib.tui.screens.agents import AgentScreen
from genlib.tui.screens.gallery import GalleryScreen
from genlib.tui.screens.jobs import JobsScreen



class GenLibTUI(App):
    TITLE = "GenLib TUI"

    BINDINGS = [
        ("c", "catalog", "Catalog"),
        ("s", "stacks", "Stacks"),
        ("a", "agents", "Agents"),
        ("g", "gallery", "Gallery"),
        ("j", "jobs", "Jobs"),
        ("q", "quit", "Quit"),
    ]

    def compose(self):
        yield Header()
        yield Footer()

    def on_mount(self):
        self.push_screen(CatalogScreen())

    def action_catalog(self):
        self.push_screen(CatalogScreen())

    def action_stacks(self):
        self.push_screen(StackScreen())

    def action_agents(self):
        self.push_screen(AgentScreen())

    def action_gallery(self):
        self.push_screen(GalleryScreen())

    def action_jobs(self):
         self.push_screen(JobsScreen())
       
