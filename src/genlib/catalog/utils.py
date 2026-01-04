from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from genlib.catalog.catalog import build_catalog
from genlib.utils import dump_json


def ensure_catalog(
    models_root: Path,
    catalog_path: Optional[str] = None,
) -> Tuple[Path, bool]:
    models_root = models_root.expanduser().resolve()
    if catalog_path:
        path = Path(catalog_path).expanduser().resolve()
    else:
        path = models_root / "catalog.json"
    if path.exists():
        return path, False
    catalog = build_catalog(models_root, include_hash=False, validate=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(path, catalog)
    return path, True
