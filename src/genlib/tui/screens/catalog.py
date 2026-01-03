from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

try:
    from rich.image import Image
except ImportError:  # rich version doesn't expose Image
    Image = None

from genlib.catalog.cache import _load_catalog
from genlib.engines.remote import CivitAIClient
from genlib.utils import DEFAULT_FORGE_MODELS_DIR, env_default


def _asset_tags(asset: Dict[str, Any]) -> List[str]:
    md = asset.get("metadata") or {}
    tags = md.get("tags") or md.get("style") or []
    if isinstance(tags, str):
        tags = [tags]
    return [str(t).lower() for t in tags]


class CatalogScreen(Screen):
    """Browse the catalog.json produced by `genlib catalog build`."""

    BINDINGS = [
        Binding("q", "app.pop_screen", "Back"),
        Binding("f", "focus_filter", "Filter"),
    ]

    def __init__(self):
        super().__init__()
        self._assets: list[Dict[str, Any]] = []
        self._row_map: dict[Any, Dict[str, Any]] = {}
        token = os.environ.get("CIVITAI_TOKEN") or os.environ.get("CIVITAI_API_KEY")
        self._civit_client = CivitAIClient(token=token)
        self._civit_cache: dict[str, Dict[str, Any]] = {}
        self._civit_fetching: set[str] = set()
        self._current_asset: Dict[str, Any] | None = None
        self._cover_cache: dict[str, Any] = {}

    def compose(self):
        with Horizontal():
            with Vertical(id="catalog-browser"):
                yield Static("Catalog Assets", id="catalog-title")
                yield Input(
                    placeholder="Filter ref/name/type/namespace/tag",
                    id="catalog-filter",
                )
                self.table = DataTable(id="catalog-table")
                self.table.add_columns(
                    "Ref",
                    "Name",
                    "Type",
                    "Namespace",
                    "Category",
                    "Size (MB)",
                    "Civit Rating",
                )
                self.table.cursor_type = "row"
                yield self.table
                yield Static("", id="catalog-status")
            with Vertical(id="catalog-detail-pane"):
                yield Static("Asset Details", id="catalog-detail-title")
                yield Static("", id="catalog-cover")
                with ScrollableContainer(id="catalog-detail-scroll"):
                    yield Static("Select an asset to see details", id="catalog-detail")

    def on_mount(self):
        filter_input = self.query_one("#catalog-filter", Input)
        filter_input.focus()
        self._load_catalog()

    def action_focus_filter(self):
        self.query_one("#catalog-filter", Input).focus()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "catalog-filter":
            self._populate_table(event.value)

    def _load_catalog(self):
        root = Path(env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR)).expanduser().resolve()
        catalog_path = os.environ.get("GENLIB_CATALOG_PATH")
        status = self.query_one("#catalog-status", Static)
        try:
            catalog = _load_catalog(root, catalog_path)
        except SystemExit as exc:
            status.update(str(exc))
            return

        self._assets = catalog.get("assets", [])
        self._populate_table()
        status.update(
            f"Loaded {len(self._assets)} assets from {catalog.get('root') or root}"
        )

    def _populate_table(self, query: str | None = None):
        table = self.table
        table.clear()
        self._row_map.clear()

        needle = (query or "").strip().lower()
        first_key: str | None = None
        matches = 0
        for asset in sorted(self._assets, key=lambda a: a.get("ref") or ""):
            if needle:
                haystack = " ".join(
                    [
                        asset.get("ref", ""),
                        asset.get("filename", ""),
                        asset.get("namespace", ""),
                        " ".join(_asset_tags(asset)),
                        ((asset.get("metadata") or {}).get("name") or ""),
                    ]
                ).lower()
                if needle not in haystack:
                    continue
            ref = asset.get("ref") or asset.get("filename") or "unknown"
            metadata = asset.get("metadata") or {}
            name = metadata.get("name") or asset.get("filename") or ref
            civit_score = self._asset_rating(asset)
            row_key = table.add_row(
                ref,
                name,
                asset.get("type") or "unknown",
                asset.get("namespace") or "unknown",
                asset.get("category") or "unknown",
                f"{asset.get('size_mb', 0):.2f}",
                civit_score,
            )
            self._row_map[row_key] = asset
            matches += 1
            if first_key is None:
                first_key = row_key

        status = self.query_one("#catalog-status", Static)
        status.update(f"{matches} assets displayed (filter: {needle or 'none'})")

        if first_key:
            self._update_detail(self._row_map[first_key])
        else:
            self._clear_detail()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        asset = self._row_map.get(event.row_key)
        if asset:
            self._update_detail(asset)

    def _update_detail(self, asset: Dict[str, Any]):
        detail = self.query_one("#catalog-detail", Static)
        metadata = asset.get("metadata") or {}
        self._current_asset = asset
        lines = [
            f"Ref: {asset.get('ref')}",
            f"Filename: {asset.get('filename')}",
            f"Relative path: {asset.get('relative_path')}",
            f"Namespace: {asset.get('namespace')}",
            f"Type: {asset.get('type')}",
            f"Category: {asset.get('category')}",
            f"Size: {asset.get('size_mb')} MB",
            f"Tags: {', '.join(_asset_tags(asset)) or 'none'}",
            f"Warnings: {', '.join(asset.get('warnings') or []) or 'none'}",
            "",
            "Metadata:",
            json.dumps(metadata or {}, indent=2),
        ]
        self._append_civit_info(lines, metadata)
        detail.update("\n".join(lines))
        self._update_cover(metadata)

    def _clear_detail(self):
        self._current_asset = None
        self._current_asset = None
        self.query_one("#catalog-cover", Static).update("")
        self.query_one("#catalog-detail", Static).update("No asset selected.")

    def _append_civit_info(self, lines: list[str], metadata: dict[str, Any]):
        civit_meta = metadata.get("civitai") or {}
        model_id = str(civit_meta.get("model_id") or civit_meta.get("modelId") or "")
        if not model_id:
            return
        cached = self._civit_cache.get(model_id)
        if cached:
            self._render_civit_lines(lines, cached, civit_meta)
        else:
            self._schedule_civit_fetch(model_id, civit_meta)

    def _schedule_civit_fetch(self, model_id: str, civit_meta: dict[str, Any]):
        if model_id in self._civit_cache or model_id in self._civit_fetching:
            return
        self._civit_fetching.add(model_id)

        def run_fetch():
            try:
                info = self._civit_client.get_model(model_id)
            except Exception as exc:
                info = {"error": str(exc)}

            def finish():
                self._civit_cache[model_id] = info
                self._civit_fetching.discard(model_id)
                if self._current_asset and str(
                    (self._current_asset.get("metadata") or {}).get("civitai", {}).get("model_id")
                ) == model_id:
                    self._update_detail(self._current_asset)

            self.call_from_thread(finish)

        threading.Thread(target=run_fetch, daemon=True).start()

    def _render_civit_lines(self, lines: list[str], info: dict[str, Any], civit_meta: dict[str, Any]):
        lines.append("")
        if info.get("error"):
            lines.append(f"CivitAI error: {info['error']}")
            return
        lines.append("[bold]CivitAI Card[/bold]")
        lines.append(f"Model ID: {info.get('id') or civit_meta.get('model_id')}")
        version = (info.get("modelVersions") or [])[:1]
        version_name = version[0].get("name") if version else civit_meta.get("version_id")
        lines.append(f"Version: {version_name}")
        cover = (version[0].get("images") or [{}])[0].get("url") if version else civit_meta.get("cover_url")
        if cover:
            lines.append(f"Cover: {cover}")
        description = info.get("description") or info.get("summary")
        if description:
            lines.append(f"Description: {description.strip().splitlines()[0][:120]}{'...' if len(description) > 120 else ''}")
        stats = info.get("stats") or {}
        rating = stats.get("rating")
        rating_count = stats.get("ratingCount")
        lines.append(
            f"Rating: {rating or 'n/a'} ({rating_count or '0'} votes)"
        )
        lines.append(
            f"Downloads: {stats.get('downloadCount', 'n/a')}, Favorites: {stats.get('favoriteCount', 'n/a')}"
        )

    def _asset_rating(self, asset: Dict[str, Any]) -> str:
        md = asset.get("metadata") or {}
        card = md.get("civit_card") or (md.get("civitai") or {})
        if card:
            rating = card.get("rating")
            votes = card.get("ratingCount") or card.get("rating_count")
            if rating is not None:
                return f"{rating:.2f} ({votes or 0})"
        return "n/a"

    def _update_cover(self, metadata: dict[str, Any]):
        cover_static = self.query_one("#catalog-cover", Static)
        cover_url = (
            (metadata.get("civit_card") or {}).get("cover_url")
            or (metadata.get("civitai") or {}).get("cover_url")
        )
        if not cover_url:
            cover_static.update("")
            return

        existing = self._cover_cache.get(cover_url)
        if existing:
            cover_static.update(existing)
            return

        if Image is None:
            cover_static.update(f"[link={cover_url}]Cover image[/link]")
            return

        def render_cover():
            try:
                img = Image.from_url(cover_url, width=60)
            except Exception:
                img = f"[link={cover_url}]Cover image[/link]"

            def done():
                cover_static.update(img)
                self._cover_cache[cover_url] = img

            self.call_from_thread(done)

        threading.Thread(target=render_cover, daemon=True).start()
