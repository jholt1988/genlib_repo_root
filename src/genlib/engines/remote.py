from __future__ import annotations
import os, re, json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from genlib.utils import cache_dir, cache_key, cache_get, cache_set


CIVITAI_BASE_URL = "https://civitai.com"

def _auth_headers(token: Optional[str]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}

def _http_get_json(url: str, headers: Dict[str, str]) -> Any:
    req = Request(url, headers={"Accept": "application/json", **headers}, method="GET")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

class CivitAIClient:
    def __init__(self, token: Optional[str] = None, cache_ttl_seconds: int = 86400):
        self.token = token
        self.cache_ttl_seconds = cache_ttl_seconds

    def get_model(self, model_id: str) -> Dict[str, Any]:
        cache_params = {"endpoint": "model", "model_id": model_id}
        cache_path = cache_dir() / cache_key("civitai_model", cache_params)
        cached = cache_get(cache_path, self.cache_ttl_seconds)
        if cached is not None:
            return {"_cached": True, **cached}
        url = f"{CIVITAI_BASE_URL}/api/v1/models/{model_id}"
        data = _http_get_json(url, _auth_headers(self.token))
        cache_set(cache_path, data)
        return {"_cached": False, **data}

def scaffold_metadata(model: Dict[str, Any]) -> Dict[str, Any]:
    # Pull best-effort fields from CivitAI response
    base_model = None
    mv = (model.get("modelVersions") or [])
    if mv:
        base_model = mv[0].get("baseModel")

    mtype = model.get("type", "").lower()
    if mtype == "lora":
        atype = "lora"
    elif mtype == "checkpoint":
        atype = "checkpoint"
    else:
        atype = "unknown"

    return {
        "name": model.get("name"),
        "type": atype,
        "base_model": base_model,
        "tags": model.get("tags") or [],
        "nsfw": bool(model.get("nsfw")),
        "source": "CivitAI",
        "civitai": {
            "model_id": model.get("id"),
            "url": model.get("url"),
        },
        # Human-edit fields:
        "default_weight": 0.75 if atype == "lora" else None,
        "avoid_with": [],
        "works_best_with": [],
        "notes": ""
    }

def remote_cli(parser):
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="Get CivitAI model info")
    info.add_argument("model_id")
    info.set_defaults(func=info_cmd)

    scaffold = sub.add_parser("scaffold", help="Generate metadata JSON scaffold from CivitAI modelId")
    scaffold.add_argument("model_id")
    scaffold.add_argument("--out", required=True, help="Path to write .json metadata")
    scaffold.set_defaults(func=scaffold_cmd)

def _client() -> CivitAIClient:
    token = os.environ.get("CIVITAI_TOKEN") or os.environ.get("CIVITAI_API_KEY")
    return CivitAIClient(token=token)

def info_cmd(args):
    c = _client()
    data = c.get_model(args.model_id)
    print(json.dumps(data, indent=2))

def scaffold_cmd(args):
    c = _client()
    model = c.get_model(args.model_id)
    meta = scaffold_metadata(model)
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"✅ Metadata scaffold written to {out}")

def search_cmd