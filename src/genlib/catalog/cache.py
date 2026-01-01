from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from genlib.utils import dump_json, load_json, env_default, DEFAULT_FORGE_MODELS_DIR, BASE_MODEL_TO_NS, sha256
from genlib.schemas.base import validate_metadata

ASSET_EXTENSIONS: Set[str] = {".safetensors", ".ckpt", ".pt", ".bin", ".pth"}


def _resolve_catalog_path(root: Path, catalog_path: Optional[str]) -> Path:
    return Path(catalog_path).expanduser().resolve() if catalog_path else (root / "catalog.json")


def _load_catalog(root: Path, catalog_path: Optional[str]) -> Dict:
    path = _resolve_catalog_path(root, catalog_path)
    if not path.exists():
        raise SystemExit(f"ERROR: catalog not found at {path}. Run: genlib catalog build --root {root}")
    return load_json(path)