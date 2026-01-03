from __future__ import annotations
import os, re, json
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from genlib.utils import cache_dir, cache_key, cache_get, cache_set


CIVITAI_BASE_URL = "https://civitai.com"
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

token = os.environ.get("TOKEN")

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
    search.add_argument("--tag", type=str, help="Comma-separated list of tags to filter by.")
    search.add_argument("--types", type=str, help="Type of Model (i.e checkpoint, LORA, VAE)")
    search.set_defaults(func=search_cmd)

    # New command: download model into sd-forge directory based on type
    download = sub.add_parser("download", help="Download a model's primary file into sd-forge appropriate directory (loras/checkpoints)")
    download.add_argument("model_id", help="CivitAI model id")
    download.add_argument("--version-id", type=int, dest="version_id", help="Specific modelVersion id (optional)")
    download.add_argument("--out-dir", help="Override sd-forge base directory (defaults to $SD_FORGE_DIR or ~/.sd-forge)")
    download.add_argument("--force", action="store_true", help="Overwrite existing file if present")
    download.set_defaults(func=download_cmd)

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

    if getattr(args, "tag", None) is not None:
        params["tag"] = args.tag

    if getattr(args, "types", None) is not None:
        params["types"] = args.types

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
    base = f"{CIVITAI_BASE_URL}/api/v1/models"
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


# --- New helpers for downloading models into sd-forge ---

def _choose_version(model: Dict[str, Any], version_id: Optional[int]) -> Optional[Dict[str, Any]]:
    versions = model.get("modelVersions") or []
    if not versions:
        return None
    if version_id is not None:
        for v in versions:
            if v.get("id") == int(version_id) or v.get("id") == version_id:
                return v
        # not found
        return None
    # prefer the first (API often orders by newest)
    return versions[0]

def _choose_file_for_version(version: Dict[str, Any], model_type_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Heuristic to pick the best file from a modelVersion.
    Prefers safetensors, then ckpt/pt/pth, and for lora hints filenames containing 'lora'.
    """
    files = version.get("files") or []
    if not files:
        return None

    # Normalize file entries
    def filename(f):
        return (f.get("name") or f.get("fileName") or "").lower()

    # candidate scoring
    preferred_exts = [".safetensors", ".ckpt", ".pt", ".pth", ".bin"]
    candidates: list[Tuple[int, Dict[str, Any]]] = []

    for f in files:
        fname = filename(f)
        score = 0
        # prefer lora-identifying filenames if model_type_hint == "lora"
        if model_type_hint == "lora" and "lora" in fname:
            score += 50
        # extension preference
        for i, ext in enumerate(preferred_exts):
            if fname.endswith(ext):
                score += (100 - i)  # earlier ext = higher score
                break
        # small bonus for shorter file names (heuristic for primary file)
        score += max(0, 10 - len(fname.split()))
        candidates.append((score, f))

    # fallback: if no ext matched, return first file
    if not any(c[0] for c in candidates):
        return files[0]

    # return highest score
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def _sd_forge_base(out_dir: Optional[str]) -> Path:
    # Allow override via arg, then env var, then default ~/.sd-forge
    if out_dir:
        base = Path(out_dir)
    else:
        base = Path(os.environ.get("SD_FORGE_DIR", "~/.sd-forge")).expanduser()
    return base

def _target_path_for_model(
    base: Path,
    model: Dict[str, Any],
    version: Dict[str, Any],
    file_entry: Dict[str, Any],
) -> Path:
    mtype = (model.get("type") or "").lower().strip()

    # ---- API type → Forge folder mapping ----
    if mtype in {"lora", "lycoris", "locon", "loha"}:
        sub = Path("models/Lora")

    elif mtype in {"checkpoint", "model", "sd", "sdxl"}:
        sub = Path("models/Stable-diffusion")

    elif mtype in {"textualinversion", "textual_inversion", "embedding"}:
        sub = Path("embeddings")

    elif mtype == "hypernetwork":
        sub = Path("models/hypernetworks")

    elif mtype in {"controlnet", "pose", "openpose", "dwpose"}:
        sub = Path("models/ControlNet")

    elif mtype == "vae":
        sub = Path("models/VAE")

    elif mtype in {"vae-approx", "vae_approx"}:
        sub = Path("models/VAE-approx")

    elif mtype in {"esrgan", "upscaler"}:
        sub = Path("models/ESRGAN")

    elif mtype == "svd":
        sub = Path("models/svd")

    elif mtype in {"text_encoder", "clip"}:
        sub = Path("models/text_encoder")

    elif mtype in {"z123", "zero123"}:
        sub = Path("models/z123")

    elif mtype == "deepbooru":
        sub = Path("models/deepbooru")

    elif mtype == "karlo":
        sub = Path("models/karlo")

    else:
        # Unknown / future types
        sub = Path("models/_unsorted")

    # ---- Ensure directories exist ----
    dest_dir = base / sub
    dest_dir.mkdir(parents=True, exist_ok=True)

    # ---- Determine filename ----
    fname = (
        file_entry.get("name")
        or file_entry.get("fileName")
        or ""
    )

    if not fname:
        url = file_entry.get("downloadUrl") or file_entry.get("url") or ""
        parsed = urlparse(url)
        fname = Path(parsed.path).name

    if not fname:
        fname = f"{model.get('id')}-{version.get('id')}"

    return dest_dir / fname

def _download_url_to_file(url: str, headers: Dict[str, str], dest: Path, force: bool = False) -> None:
    if dest.exists() and not force:
        print(f"File already exists: {dest} (use --force to overwrite)")
        return
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=120) as r:
        # Attempt streaming write
        dest_tmp = dest.with_suffix(dest.suffix + ".part")
        with open(dest_tmp, "wb") as fh:
            chunk_size = 64 * 1024
            while True:
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
        dest_tmp.rename(dest)
    print(f"✅ Downloaded to {dest}")


def download_cmd(args):
    """
    Download a model's primary file and place it into the sd-forge directory
    under models/loras or models/checkpoints depending on type.
    """
    client = _client()
    model = client.get_model(args.model_id)
    # API wrapper may include a _cached key — keep using model dict as-is
    version = _choose_version(model, getattr(args, "version_id", None))
    if version is None:
        print("No modelVersions found (or specified version not found). Aborting.")
        raise SystemExit(1)

    mtype = (model.get("type") or "").lower()
    file_entry = _choose_file_for_version(version, mtype)
    if file_entry is None:
        print("No downloadable files found for selected version. Aborting.")
        raise SystemExit(1)

    download_url = file_entry.get("downloadUrl") or file_entry.get("url") or file_entry.get("download_url")
    if not download_url:
        print("Selected file has no download URL. Aborting.")
        raise SystemExit(1)

    base = _sd_forge_base(getattr(args, "out_dir", None))
    dest = _target_path_for_model(base, model, version, file_entry)

    headers = {"User-Agent": "genlib/remote.py", **_auth_headers(client.token)}

    try:
        _download_url_to_file(download_url, headers, dest, force=bool(getattr(args, "force", False)))
    except Exception as e:
        print(f"Error downloading file: {e}")
        raise

    # Print a suggestion to the user where the file was saved and what they may want to do next.
    metadata = scaffold_metadata(model)
    civitai_meta = metadata.get("civitai", {})
    civitai_meta.update({
        "model_id": model.get("id"),
        "url": model.get("url"),
        "version_id": version.get("id"),
        "cover_url": (version.get("images") or [{}])[0].get("url") if (version.get("images")) else None,
        "author": (model.get("user") or {}).get("username"),
    })
    metadata["civitai"] = civitai_meta

    meta_path = dest.with_suffix(".json")
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            existing_civit = existing.get("civitai", {})
        except Exception:
            existing = {}
            existing_civit = {}
    else:
        existing = {}
        existing_civit = {}

    merged = {**existing, **metadata}
    merged_civit = {**existing_civit, **civitai_meta}
    merged["civitai"] = merged_civit
    meta_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"? Catalog metadata written to {meta_path}")

    print(f"Model '{model.get('name')}' (type={mtype}) version {version.get('id')} saved to {dest}")
