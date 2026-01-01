from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from genlib.utils import env_default, load_json, DEFAULT_FORGE_MODELS_DIR
from genlib.rules import compatible
from genlib.templates import render

INTENT_TAGS = {
    "portrait": ["portrait", "faces", "people"],
    "product": ["product", "studio", "commercial"],
    "landscape": ["landscape", "scenery"],
    "anime": ["anime", "illustration"],
    "realism": ["realism", "photoreal", "photo"],
}

DEFAULT_PARAMS = {"sampler": "DPM++ 2M Karras", "steps": 28, "cfg": 6}

def compose_cli(parser):
    parser.add_argument("intent", help="High-level intent (portrait, product, landscape, etc.)")
    parser.add_argument("--style", action="append", default=[], help="Style tags to bias selection (repeatable)")
    parser.add_argument("--subject", default="subject", help="Subject for prompt templates")
    parser.add_argument("--details", default="", help="Extra details for prompt templates")
    parser.add_argument("--quality", default="high quality", help='Quality phrase (e.g. "masterpiece, best quality")')
    parser.add_argument("--neg-add", default="", help="Append to negative prompt")
    parser.add_argument("--safe", action="store_true", help="Prefer SFW assets when metadata provides nsfw=false")
    parser.add_argument("--ns", default=None, help="Namespace preference (sd15, sdxl, flux)")
    parser.add_argument("--catalog", default=None, help="Path to catalog.json (default: <models_root>/catalog.json)")
    parser.add_argument("--root", default=env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR),
                        help="Models root (used only if --catalog not provided)")
    parser.add_argument("--forge", action="store_true", help="Output in Forge-ready format")
    parser.add_argument("--json", action="store_true", help="Output stack JSON")
    parser.add_argument("--explain", action="store_true", help="Explain selection decisions")
    parser.set_defaults(func=compose_cmd)

def _resolve_catalog_path(root: Path, catalog_path: Optional[str]) -> Path:
    return Path(catalog_path).expanduser().resolve() if catalog_path else (root / "catalog.json")

def _tags(asset: Dict[str, Any]) -> List[str]:
    md = asset.get("metadata") or {}
    t = md.get("tags") or md.get("style") or []
    if isinstance(t, str):
        return [t.lower()]
    return [str(x).lower() for x in t]

def _name(asset: Dict[str, Any]) -> str:
    md = asset.get("metadata") or {}
    return str(md.get("name") or asset.get("filename") or asset.get("id"))

def _forge_id(asset: Dict[str, Any]) -> str:
    md = asset.get("metadata") or {}
    return str(md.get("forge_id") or asset.get("id") or Path(asset.get("filename","")).stem).strip()

def _nsfw(asset: Dict[str, Any]) -> Optional[bool]:
    md = asset.get("metadata") or {}
    v = md.get("nsfw")
    return v if isinstance(v, bool) else None

def _score(asset: Dict[str, Any], wanted: List[str], safe: bool, ns: Optional[str]) -> Tuple[int, List[str]]:
    s = 0
    reasons: List[str] = []
    tags = _tags(asset)
    name = _name(asset).lower()
    for w in wanted:
        wl = w.lower()
        if wl in tags:
            s += 3
            reasons.append(f"tag:{wl}")
        if wl in name:
            s += 1
            reasons.append(f"name:{wl}")

    if ns and asset.get("namespace") == ns:
        s += 2
        reasons.append(f"namespace:{ns}")

    if safe and _nsfw(asset) is True:
        s -= 100
        reasons.append("nsfw:true penalty")

    return s, reasons

def _rank(cands: List[Dict[str, Any]], wanted: List[str], safe: bool, ns: Optional[str]) -> List[Dict[str, Any]]:
    rows = []
    for a in cands:
        sc, rs = _score(a, wanted, safe, ns)
        rows.append({"asset": a, "score": sc, "reasons": rs})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows

def _pick_best(ranked: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return ranked[0]["asset"] if ranked else None

def compose_cmd(args):
    result = compose_from_stack(
        stack_doc={
            "intent": args.intent,
            "prompt": {"subject": args.subject, "details": args.details, "style": args.style, "quality": args.quality, "negative_add": args.neg_add},
            "constraints": {"safe": args.safe, "namespace": args.ns},
            "selection": {"max_loras": 2, "prefer": [], "avoid": []},
            "params": DEFAULT_PARAMS,
        },
        models_root=args.root,
        catalog_path=args.catalog,
        explain=args.explain,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if args.forge:
        lora_tokens = " ".join([f"<lora:{l['forge_id']}:{l['weight']}>" for l in (result.get("loras") or [])])
        print((lora_tokens + " " + result["positive_prompt"]).strip())
        print("\n# negative")
        print(result["negative_prompt"])
        print("\n# params")
        print(json.dumps(result["params"], indent=2))
        return

    # Human output
    print(f"Base model: {result.get('base_model')} ({result.get('base_ref')})")
    if result.get("loras"):
        print("LoRAs:")
        for l in result["loras"]:
            print(f" - {l['name']} ({l['weight']}) [{l['id']}]")
    print("\nPrompt:")
    print(result["positive_prompt"])
    print("\nNegative:")
    print(result["negative_prompt"])
    print("\nParams:")
    print(json.dumps(result["params"], indent=2))

def compose_from_stack(stack_doc: Dict[str, Any], models_root: str, catalog_path: Optional[str], explain: bool = False) -> Dict[str, Any]:
    root = Path(models_root).expanduser().resolve()
    cat_path = _resolve_catalog_path(root, catalog_path)

    if not cat_path.exists():
        raise SystemExit(f"ERROR: catalog not found at {cat_path}. Run: genlib catalog build --root {root}")

    catalog = load_json(cat_path)
    assets = catalog.get("assets", [])

    intent = (stack_doc.get("intent") or "portrait").lower()
    # vars already resolved at stack layer
    prompt = stack_doc.get("prompt") or {}
    constraints = stack_doc.get("constraints") or {}
    selection = stack_doc.get("selection") or {}
    params = stack_doc.get("params") or DEFAULT_PARAMS

    safe = bool(constraints.get("safe")) if constraints.get("safe") is not None else False
    ns = constraints.get("namespace") if isinstance(constraints.get("namespace"), str) else None
    max_loras = int(selection.get("max_loras", 2) or 2)

    style = prompt.get("style") or []
    if isinstance(style, str):
        style = [style]

    wanted: List[str] = []
    wanted += INTENT_TAGS.get(intent, [intent])
    wanted += [s.lower() for s in style]
    # selection prefer/avoid biases
    prefer = selection.get("prefer") or []
    avoid = selection.get("avoid") or []
    if isinstance(prefer, str): prefer = [prefer]
    if isinstance(avoid, str): avoid = [avoid]
    wanted += [p.lower() for p in prefer]

    checkpoints = [a for a in assets if (a.get("type") == "checkpoint" or a.get("category") == "Stable-diffusion")]
    loras = [a for a in assets if (a.get("type") == "lora" or a.get("category","").lower() in ("lora", "loras"))]

    base_ranked = _rank(checkpoints, wanted, safe, ns)
    base = _pick_best(base_ranked)

    lora_ranked = _rank(loras, wanted, safe, ns)

    # Compatibility + avoid filtering + max_loras
    picked_rows = []
    for row in lora_ranked:
        if len(picked_rows) >= max_loras:
            break
        a = row["asset"]
        # avoid terms
        a_tags = set(_tags(a))
        if any(av.lower() in a_tags or av.lower() in _name(a).lower() for av in avoid):
            row["compatible"] = False
            row["compat_reasons"] = ["excluded by selection.avoid"]
            continue
        ok = True
        creas: List[str] = []
        if base:
            ok, creas = compatible(base, a)
        row["compatible"] = ok
        row["compat_reasons"] = creas
        if not ok:
            continue
        # require positive score unless it's the first
        if row["score"] <= 0 and picked_rows:
            continue
        picked_rows.append(row)

    lora_entries = []
    for row in picked_rows:
        a = row["asset"]
        md = a.get("metadata") or {}
        w = md.get("default_weight") if md.get("default_weight") is not None else md.get("weight")
        if w is None:
            w = 0.75
        try:
            w = float(w)
        except Exception:
            w = 0.75
        lora_entries.append({
            "name": _name(a),
            "id": a.get("ref") or a.get("id"),
            "forge_id": _forge_id(a),
            "weight": round(w, 2),
            "base_model": md.get("base_model") if isinstance(md.get("base_model"), str) else None,
        })

    style_str = ", ".join(style)
    prompt_bits = render(
        intent,
        subject=str(prompt.get("subject") or "subject"),
        details=str(prompt.get("details") or ""),
        style=style_str,
        quality=str(prompt.get("quality") or "high quality"),
        negative_add=str(prompt.get("negative_add") or ""),
    )

    result = {
        "intent": intent,
        "style": style,
        "safety": "sfw" if safe else "unspecified",
        "namespace_preference": ns,
        "base_model": _name(base) if base else None,
        "base_ref": (base.get("ref") if base else None),
        "loras": lora_entries,
        "positive_prompt": prompt_bits["positive"],
        "negative_prompt": prompt_bits["negative"],
        "template": prompt_bits["template"],
        "params": params,
    }

    if explain:
        _print_explain(base_ranked, lora_ranked, picked_rows, result)

    return result

def _print_explain(base_ranked, lora_ranked, picked_rows, result):
    def top(rows, n=5): return rows[:n]
    print("")
    print("=== EXPLAIN ===")
    print(f"Selected base: {result.get('base_ref')} :: {result.get('base_model')}")
    print("Top base candidates:")
    for r in top(base_ranked, 5):
        a = r["asset"]
        print(f"  score={r['score']:>4}  {a.get('ref')} :: {_name(a)}  reasons={','.join(r['reasons']) or '-'}")
    print("")
    print("Selected LoRAs:")
    for l in result.get("loras", []):
        print(f"  {l['id']} :: {l['name']}  weight={l['weight']}")
    print("Top LoRA candidates (compat shown):")
    # annotate compat for display
    picked_ids = set([pr["asset"].get("ref") or pr["asset"].get("id") for pr in picked_rows])
    for r in top(lora_ranked, 10):
        a = r["asset"]
        aid = a.get("ref") or a.get("id")
        compat = "OK" if aid in picked_ids else "--"
        reas = ",".join(r.get("reasons") or []) or "-"
        print(f"  score={r['score']:>4}  {compat:>2}  {aid} :: {_name(a)}  reasons={reas}")
    print("=== /EXPLAIN ===")
    print("")
