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

    search = sub.add_parser("search", help="Search CivitAI images with various filters")
    search.add_argument("--limit", type=int, help="Number of results per page (0-200). Default 100 if omitted.")
    search.add_argument("--post-id", type=int, dest="post_id", help="Filter to images from a specific post (postId).")
    search.add_argument("--model-id", type=int, dest="model_id", help="Filter to images from a specific model (modelId).")
    search.add_argument("--model-version-id", type=int, dest="model_version_id", help="Filter to images from a specific model version (modelVersionId).")
    search.add_argument("--username", help="Filter to images from a specific user.")
    search.add_argument("--nsfw", help="NSFW filter. Accepts None, Soft, Mature, X, true, false (case-insensitive).")
    search.add_argument("--sort", help="Sort order. Accepts 'Most Reactions', 'Most Comments', or 'Newest' (case-insensitive, spaces optional).")
    search.add_argument("--period", help="Time period. Accepts AllTime, Year, Month, Week, Day (case-insensitive).")
    search.add_argument("--page", type=int, help="Page number to fetch (1-based).")
    search.set_defaults(func=search_cmd)

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

def _normalize_sort(val: str) -> str:
    # Normalize user provided sort to API expected value
    if not val:
        return val
    v = re.sub(r"\s+", "", val).lower()
    mapping = {
        "mostreactions": "MostReactions",
        "mostcomments": "MostComments",
        "newest": "Newest",
    }
    return mapping.get(v, val)

def _normalize_period(val: str) -> str:
    if not val:
        return val
    v = val.lower()
    mapping = {
        "alltime": "AllTime",
        "year": "Year",
        "month": "Month",
        "week": "Week",
        "day": "Day",
    }
    return mapping.get(v, val)

def _normalize_nsfw(val: str) -> str:
    if val is None:
        return val
    v = val.lower()
    # Accept true/false or enum values None/Soft/Mature/X
    if v in ("true", "false"):
        return v
    mapping = {
        "none": "None",
        "soft": "Soft",
        "mature": "Mature",
        "x": "X",
    }
    return mapping.get(v, val)

def search_cmd(args):
    """
    Call the CivitAI images endpoint with the allowed filters:
    limit, postId, modelId, modelVersionId, username, nsfw, sort, period, page
    """
    params: Dict[str, Any] = {}

    # limit: clamp to [0,200] if provided
    if args.limit is not None:
        limit = max(0, min(200, int(args.limit)))
        params["limit"] = limit

    # integer IDs (use exact param names expected by API)
    if getattr(args, "post_id", None) is not None:
        params["postId"] = int(args.post_id)
    if getattr(args, "model_id", None) is not None:
        params["modelId"] = int(args.model_id)
    if getattr(args, "model_version_id", None) is not None:
        params["modelVersionId"] = int(args.model_version_id)

    # username
    if getattr(args, "username", None):
        params["username"] = args.username

    # nsfw - normalize
    if getattr(args, "nsfw", None) is not None:
        nsfw_val = _normalize_nsfw(args.nsfw)
        # only set if normalization produced a usable value
        if nsfw_val is not None:
            params["nsfw"] = nsfw_val

    # sort - normalize to API expected values
    if getattr(args, "sort", None):
        params["sort"] = _normalize_sort(args.sort)

    # period - normalize
    if getattr(args, "period", None):
        params["period"] = _normalize_period(args.period)

    # page
    if getattr(args, "page", None) is not None:
        # API expects page number (1-based). Ensure it's at least 1.
        page = max(1, int(args.page))
        params["page"] = page

    # Build URL with query string
    base = f"{CIVITAI_BASE_URL}/api/v1/images"
    if params:
        qs = urlencode(params)
        url = f"{base}?{qs}"
    else:
        url = base

    # Make request
    client = _client()
    try:
        data = _http_get_json(url, _auth_headers(client.token))
    except Exception as e:
        # Provide a concise error message useful for CLI users
        print(f"Error fetching from CivitAI: {e}")
        raise

    # Print result
    print(json.dumps(data, indent=2))