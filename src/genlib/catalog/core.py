from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from genlib.utils import dump_json, load_json, env_default, DEFAULT_FORGE_MODELS_DIR, BASE_MODEL_TO_NS, sha256
from genlib.schemas.base import validate_metadata


ASSET_EXTENSIONS: Set[str] = {".safetensors", ".ckpt", ".pt", ".bin", ".pth"}

def _category(root: Path, p: Path) -> str:
    rel = p.relative_to(root)
    return rel.parts[0] if rel.parts else "unknown"

def _stem(p: Path) -> str:
    return p.stem

def _namespace(md: Optional[Dict]) -> str:
    if not md:
        return "unknown"
    base = md.get("base_model")
    return BASE_MODEL_TO_NS.get(base, "unknown")
