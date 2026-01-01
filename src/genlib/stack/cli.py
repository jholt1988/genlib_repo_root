from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from genlib.utils import env_default, DEFAULT_FORGE_MODELS_DIR, dump_json, load_json
from genlib.schemas.stack import validate_stack

DEFAULT_STACKS_DIR = "stacks"
DEFAULT_BUILD_DIR = "stacks/.build"

BASE_STACKS = {
    "portrait_base": {
        "name": "portrait_base",
        "version": "1.0.0",
        "intent": "portrait",
        "prompt": {
            "subject": "subject",
            "details": "",
            "style": [],
            "quality": "high quality",
            "negative_add": "extra fingers, distorted hands"
        },
        "constraints": {"safe": True, "namespace": None},
        "selection": {"max_loras": 2, "prefer": [], "avoid": []},
        "params": {"sampler": "DPM++ 2M Karras", "steps": 28, "cfg": 6},
        "notes": "Base portrait stack"
    },
    "product_base": {
        "name": "product_base",
        "version": "1.0.0",
        "intent": "product",
        "prompt": {
            "subject": "product",
            "details": "",
            "style": [],
            "quality": "high quality",
            "negative_add": "cluttered background"
        },
        "constraints": {"safe": True, "namespace": None},
        "selection": {"max_loras": 1, "prefer": [], "avoid": []},
        "params": {"sampler": "DPM++ 2M Karras", "steps": 26, "cfg": 6},
        "notes": "Base product stack"
    },
    "landscape_base": {
        "name": "landscape_base",
        "version": "1.0.0",
        "intent": "landscape",
        "prompt": {
            "subject": "landscape",
            "details": "",
            "style": [],
            "quality": "high quality",
            "negative_add": "tilted horizon"
        },
        "constraints": {"safe": True, "namespace": None},
        "selection": {"max_loras": 1, "prefer": [], "avoid": []},
        "params": {"sampler": "DPM++ 2M Karras", "steps": 30, "cfg": 6},
        "notes": "Base landscape stack"
    }
}

def stack_cli(parser):
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create a new stack file scaffold")
    new.add_argument("name")
    new.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    new.add_argument("--extends", default=None)
    new.add_argument("--intent", default=None)
    new.add_argument("--vars",
    dest="vars",
    action="append",
    help="Declare variable as name:type")
    new.add_argument( "--preset",
    dest="presets",
    action="append",
    help="Create empty preset")
    new.set_defaults(func=new_cmd)

    init = sub.add_parser("init", help="Initialize stacks directory with base stacks")
    init.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    init.set_defaults(func=init_cmd)

    validate = sub.add_parser("validate", help="Validate stack files")
    validate.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    validate.add_argument("--name", default=None, help="Validate only one stack")
    validate.set_defaults(func=validate_cmd)

    ls = sub.add_parser("list", help="List stack files")
    ls.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    ls.set_defaults(func=list_cmd)

    show = sub.add_parser("show", help="Show a stack (raw or resolved)")
    show.add_argument("name")
    show.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    show.add_argument("--resolved", action="store_true")
    show.set_defaults(func=show_cmd)

    build = sub.add_parser("build", help="Resolve stack inheritance and produce a resolved stack artifact")
    build.add_argument("name")
    build.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    build.add_argument("--outdir", default=DEFAULT_BUILD_DIR)
    build.set_defaults(func=build_cmd)

    run = sub.add_parser("run", help="Build a stack then emit Forge-ready output")
    run.add_argument("name")
    run.add_argument("--dir", default=DEFAULT_STACKS_DIR)
    run.add_argument("--outdir", default=DEFAULT_BUILD_DIR)
    run.add_argument("--forge", action="store_true")
    run.add_argument("--json", action="store_true")
    run.add_argument("--explain", action="store_true")
    run.add_argument("--engine", default="none", choices=["none","forge"], help="Execution engine")
    run.add_argument("--forge-dir", default=None, help="Path to stable-diffusion-webui-forge")
    run.add_argument("--out", default=None, help="Output directory template, e.g. outputs/{stack}/{mood}/{lens}")
    run.add_argument("--seed", default=None, help="Seed or comma list for batching")
    run.add_argument("--preset", action="append", default=[], help="Preset name (repeatable)")
    run.add_argument("--var", action="append", default=[], help="VAR=VALUE")
    run.add_argument("--vars", default=None, help="Path to JSON vars file")
    run.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR))
    run.add_argument("--catalog", default=None)
    run.set_defaults(func=run_cmd)

# --- helpers (reuse from v1.0) ---

def _stack_path(stacks_dir: Path, name: str) -> Path:
    if not name.endswith(".json"):
        name += ".json"
    return stacks_dir / name

def _load_stack(stacks_dir: Path, name: str) -> Dict[str, Any]:
    path = _stack_path(stacks_dir, name)
    if not path.exists():
        raise SystemExit(f"Stack not found: {path}")
    doc = load_json(path)
    errs = validate_stack(doc)
    if errs:
        raise SystemExit("Invalid stack file:\n" + "\n".join(f"- {e}" for e in errs))
    return doc

def _merge(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(parent)
    for k, v in child.items():
        if v is None:
            continue
        if k in ("prompt", "constraints", "selection", "params") and isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v

    def norm_list(x):
        if x is None: return []
        if isinstance(x, str): return [x]
        if isinstance(x, list): return x
        return [str(x)]

    if isinstance(out.get("prompt"), dict):
        out["prompt"]["style"] = norm_list(out["prompt"].get("style"))
    if isinstance(out.get("selection"), dict):
        for lk in ("prefer", "avoid"):
            out["selection"][lk] = norm_list(out["selection"].get(lk))
    return out

def resolve_stack(stacks_dir: Path, name: str, *, max_depth: int = 10) -> Tuple[Dict[str, Any], List[str]]:
    chain = []
    doc = _load_stack(stacks_dir, name)
    chain.append(doc["name"])
    depth = 0
    while doc.get("extends"):
        depth += 1
        if depth > max_depth:
            raise SystemExit("Stack inheritance too deep (possible cycle)")
        parent = _load_stack(stacks_dir, doc["extends"])
        chain.append(parent["name"])
        doc = _merge(parent, doc)
    return doc, list(reversed(chain))

# --- commands ---


# reuse list_cmd, show_cmd, build_cmd, run_cmd from v1.0
from genlib.stack.commands import list_cmd, show_cmd, build_cmd, run_cmd, init_cmd, validate_cmd,new_cmd
