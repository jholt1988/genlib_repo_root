from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from genlib.engines.remote import CivitAIClient
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

def _should_prefetch_metadata(
    md: Optional[Dict[str, Any]],
    tags: list[str] | None,
    base: str | None,
) -> bool:
    if not md:
        return False
    if base:
        base_model = (md.get("base_model") or "").lower()
        if base_model != base.lower():
            return False
    if tags:
        asset_tags = [str(t).lower() for t in (md.get("tags") or [])]
        if not any(tag in asset_tags for tag in tags):
            return False
    return True


def _civit_card(client: CivitAIClient, model_id: str) -> Dict[str, Any] | None:
    try:
        card = client.get_model(model_id)
    except Exception:
        return None
    versions = card.get("modelVersions") or []
    version = versions[0] if versions else {}
    stats = card.get("stats") or {}
    return {
        "model_id": card.get("id"),
        "name": card.get("name"),
        "cover_url": (version.get("images") or [{}])[0].get("url") if version else None,
        "description": card.get("description") or card.get("summary"),
        "downloadCount": stats.get("downloadCount"),
        "favoriteCount": stats.get("favoriteCount"),
        "rating": stats.get("rating"),
        "ratingCount": stats.get("ratingCount"),
        "url": card.get("url"),
    }


def build_catalog(
    root: Path,
    *,
    include_hash: bool = True,
    validate: bool = True,
    civit_prefetch_limit: int | None = None,
    civit_prefetch_tags: list[str] | None = None,
    civit_prefetch_base: str | None = None,
) -> Dict:
    assets: List[Dict] = []
    token = os.environ.get("CIVITAI_TOKEN") or os.environ.get("CIVITAI_API_KEY")
    client = CivitAIClient(token=token) if token else None
    _prefetched_count = 0
    for p in root.rglob("*"):
        if not (p.is_file() and p.suffix.lower() in ASSET_EXTENSIONS):
            continue

        meta_path = p.with_suffix(".json")
        md = None
        warnings: List[str] = []

        if meta_path.exists():
            try:
                md = json.loads(meta_path.read_text(encoding="utf-8"))
                if validate:
                    warnings.extend(validate_metadata(md))
            except Exception as e:
                warnings.append(f"invalid_metadata:{e}")
        else:
            warnings.append("missing_metadata")

        aid = _stem(p)
        ns = _namespace(md)
        aref = f"{ns}:{aid}" if ns != "unknown" else aid

        if client and md:
            civitai_md = md.get("civitai") or {}
            model_id = civitai_md.get("model_id") or civitai_md.get("modelId")
            if model_id:
                if _should_prefetch_metadata(md, civit_prefetch_tags, civit_prefetch_base):
                    if civit_prefetch_limit is None or _prefetched_count < civit_prefetch_limit:
                        card = _civit_card(client, str(model_id))
                        if card:
                            md["civit_card"] = card
                            _prefetched_count += 1

        assets.append({
            "id": aid,
            "namespace": ns,
            "ref": aref,
            "filename": p.name,
            "relative_path": str(p.relative_to(root)),
            "category": _category(root, p),
            "type": (md or {}).get("type", "unknown"),
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "sha256": sha256(p) if include_hash else None,
            "metadata": md,
            "warnings": warnings,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "asset_count": len(assets),
        "assets": assets,
    }

def _resolve_catalog_path(root: Path, catalog_path: Optional[str]) -> Path:
    return Path(catalog_path).expanduser().resolve() if catalog_path else (root / "catalog.json")

def catalog_cli(parser):
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build catalog.json from your models directory")
    build.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR))
    build.add_argument("--output", default=None)
    build.add_argument("--no-hash", action="store_true")
    build.add_argument("--no-validate", action="store_true")
    build.set_defaults(func=build_cmd)

    search = sub.add_parser("search", help="Search local catalog")
    search.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR))
    search.add_argument("--catalog", default=None)
    search.add_argument("--type", dest="atype", default=None)
    search.add_argument("--tag", default=None)
    search.add_argument("--ns", default=None, help="Namespace (sd15, sdxl, flux)")
    search.add_argument("--name", default=None, help="Substring match filename or metadata.name")
    search.add_argument("--limit", type=int, default=50)
    search.set_defaults(func=search_cmd)

    show = sub.add_parser("show", help="Show asset details by ref/id/filename/name")
    show.add_argument("query")
    show.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR))
    show.add_argument("--catalog", default=None)
    show.set_defaults(func=show_cmd)

def build_cmd(args):
    root = Path(args.root).expanduser().resolve()
    out = Path(args.output).expanduser().resolve() if args.output else (root / "catalog.json")
    cat = build_catalog(root, include_hash=(not args.no_hash), validate=(not args.no_validate))
    dump_json(out, cat)
    print(f"✅ Catalog generated: {out}")
    # surface validation issues count
    warn = sum(1 for a in cat["assets"] if a.get("warnings"))
    print(f"📦 Assets indexed: {cat['asset_count']} (assets with warnings: {warn})")

def _load_catalog(root: Path, catalog_path: Optional[str]) -> Dict:
    path = _resolve_catalog_path(root, catalog_path)
    if not path.exists():
        raise SystemExit(f"ERROR: catalog not found at {path}. Run: genlib catalog build --root {root}")
    return load_json(path)

def _tags(asset: Dict) -> List[str]:
    md = asset.get("metadata") or {}
    t = md.get("tags") or md.get("style") or []
    if isinstance(t, str):
        return [t.lower()]
    return [str(x).lower() for x in t]

def search_cmd(args):
    root = Path(args.root).expanduser().resolve()
    cat = _load_catalog(root, args.catalog)
    assets = cat.get("assets", [])

    out = []
    for a in assets:
        if args.atype and a.get("type") != args.atype:
            continue
        if args.ns and a.get("namespace") != args.ns:
            continue
        if args.tag and args.tag.lower() not in _tags(a):
            continue
        if args.name:
            mdn = ((a.get("metadata") or {}).get("name") or "")
            hay = (a.get("filename","") + " " + mdn + " " + a.get("ref","")).lower()
            if args.name.lower() not in hay:
                continue
        out.append(a)

    for a in out[: args.limit]:
        md = a.get("metadata") or {}
        label = md.get("name") or a.get("filename")
        warn = " ⚠️" if a.get("warnings") else ""
        print(f"- {a.get('ref')} :: {label} ({a.get('type')}){warn} [{a.get('relative_path')}]")
    if len(out) > args.limit:
        print(f"…and {len(out)-args.limit} more")
    print(f"Found {len(out)} match(es)")

def show_cmd(args):
    root = Path(args.root).expanduser().resolve()
    cat = _load_catalog(root, args.catalog)
    q = args.query.lower()

    hits = []
    for a in cat.get("assets", []):
        md = a.get("metadata") or {}
        if q in {
            str(a.get("ref","")).lower(),
            str(a.get("id","")).lower(),
            str(a.get("filename","")).lower(),
            str(md.get("name","")).lower(),
        }:
            hits.append(a)

    if not hits:
        # substring fallback
        for a in cat.get("assets", []):
            md = a.get("metadata") or {}
            hay = (a.get("ref","") + " " + a.get("filename","") + " " + str(md.get("name",""))).lower()
            if q in hay:
                hits.append(a)

    if not hits:
        raise SystemExit(f"No asset found matching: {args.query}")

    print(json.dumps(hits if len(hits) > 1 else hits[0], indent=2))
