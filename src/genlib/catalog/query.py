from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from genlib.utils import dump_json, load_json, env_default, DEFAULT_FORGE_MODELS_DIR, BASE_MODEL_TO_NS, sha256
from genlib.schemas.base import validate_metadata

ASSET_EXTENSIONS: Set[str] = {".safetensors", ".ckpt", ".pt", ".bin", ".pth"}


def _tags(asset: Dict) -> List[str]:
    md = asset.get("metadata") or {}
    t = md.get("tags") or md.get("style") or []
    if isinstance(t, str):
        return [t.lower()]
    return [str(x).lower() for x in t]
