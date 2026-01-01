import json
import os
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_FORGE_MODELS_DIR = "/home/jholt/stable-diffusion-webui-forge/models"

BASE_MODEL_TO_NS = {
    "SD 1.5": "sd15",
    "SDXL": "sdxl",
    "Flux": "flux",
}

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def env_default(key: str, fallback: str) -> str:
    return os.environ.get(key, fallback)

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    p = Path(base) / "genlib"
    p.mkdir(parents=True, exist_ok=True)
    return p

def cache_key(prefix: str, params: Dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()[:24]
    return f"{prefix}_{h}.json"

def cache_get(path: Path, ttl_seconds: int) -> Optional[Any]:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if ttl_seconds <= 0 or age > ttl_seconds:
        return None
    try:
        return load_json(path)
    except Exception:
        return None

def cache_set(path: Path, data: Any) -> None:
    dump_json(path, data)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
