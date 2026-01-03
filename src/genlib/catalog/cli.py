from genlib.catalog.index import build_catalog
from genlib.catalog.cache import _load_catalog
from genlib.catalog.query import _tags
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from genlib.utils import dump_json, load_json, env_default, DEFAULT_FORGE_MODELS_DIR, BASE_MODEL_TO_NS, sha256


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



def catalog_cli(parser):
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build catalog.json from your models directory")
    build.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR))
    build.add_argument("--output", default=None)
    build.add_argument("--no-hash", action="store_true")
    build.add_argument("--no-validate", action="store_true")
    build.add_argument(
        "--civit-limit",
        type=int,
        default=None,
        help="Max assets to prefetch CivitAI cards for (default: unlimited)",
    )
    build.add_argument(
        "--civit-tags",
        default=None,
        help="Comma-separated tags to filter which assets get CivitAI prefetch",
    )
    build.add_argument(
        "--civit-base",
        default=None,
        help="Only prefetch CivitAI cards for assets whose metadata base_model matches",
    )
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
    civit_tags = None
    if args.civit_tags:
        civit_tags = [t.strip().lower() for t in args.civit_tags.split(",") if t.strip()]
    cat = build_catalog(
        root,
        include_hash=(not args.no_hash),
        validate=(not args.no_validate),
        civit_prefetch_limit=args.civit_limit,
        civit_prefetch_tags=civit_tags,
        civit_prefetch_base=args.civit_base,
    )
    dump_json(out, cat)
    print(f"✅ Catalog generated: {out}")
    # surface validation issues count
    warn = sum(1 for a in cat["assets"] if a.get("warnings"))
    print(f"📦 Assets indexed: {cat['asset_count']} (assets with warnings: {warn})")
