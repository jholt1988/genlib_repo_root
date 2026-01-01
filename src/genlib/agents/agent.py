from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import re, json

# Deterministic planner: natural language -> execution plan.
# It can optionally "run" by invoking the stack runner with computed args.

INTENT_MAP = {
    "portrait": ["portrait", "person", "face", "headshot"],
    "product": ["product", "packshot", "ecommerce"],
    "landscape": ["landscape", "scenery", "mountain", "forest", "ocean"],
    "anime": ["anime", "manga", "waifu"],
}

MOOD_MAP = {
    "cinematic": ["cinematic", "film", "movie"],
    "soft": ["soft", "gentle", "diffused"],
    "dramatic": ["dramatic", "high contrast", "chiaroscuro"],
    "lowlight": ["lowlight", "night", "dark"],
}

def infer_intent(text: str) -> str:
    t = text.lower()
    for intent, keys in INTENT_MAP.items():
        if any(k in t for k in keys):
            return intent
    return "portrait"

def infer_count(text: str, default: int = 1) -> int:
    t = text.lower()
    m = re.search(r"(\d+)\s*(?:variations|variants|images|pics|outputs)", t)
    if m:
        try:
            n = int(m.group(1))
            return max(1, min(n, 200))
        except Exception:
            return default
    return default

def infer_vars(text: str) -> Dict[str, Any]:
    t = text.lower()
    vars: Dict[str, Any] = {}

    moods = []
    for mood, keys in MOOD_MAP.items():
        if any(k in t for k in keys):
            moods.append(mood if mood in ("cinematic","soft","dramatic") else mood)
    # Normalize: lowlight is better as preset hint; mood stays cinematic/soft/dramatic if present.
    if moods:
        primary = None
        for m in ("cinematic","soft","dramatic"):
            if m in moods:
                primary = m
                break
        if primary:
            vars["mood"] = primary

    lens = re.findall(r"\b(\d{2})mm\b", t)
    if lens:
        # if multiple lenses mentioned, batch them
        uniq = []
        for x in lens:
            val = f"{x}mm"
            if val not in uniq:
                uniq.append(val)
        vars["lens"] = ",".join(uniq) if len(uniq) > 1 else uniq[0]

    # subject heuristics
    if "man" in t or "male" in t:
        vars["subject"] = "a man"
    if "woman" in t or "female" in t:
        vars["subject"] = "a woman"
    if "couple" in t:
        vars["subject"] = "a couple"

    return vars

def infer_safety(text: str) -> bool:
    t = text.lower()
    if any(x in t for x in ["nsfw", "explicit", "porn", "nude", "nudity"]):
        return False
    return True

def discover_stacks(stacks_dir: Path) -> List[Dict[str, Any]]:
    stacks: List[Dict[str, Any]] = []
    if not stacks_dir.exists():
        return stacks
    for p in stacks_dir.glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            name = doc.get("name") or p.stem
            stacks.append({"name": name, "path": p, "doc": doc})
        except Exception:
            continue
    return stacks

def choose_stack(stacks: List[Dict[str, Any]], intent: str, text: str) -> str:
    # Prefer intent-specific specialized stacks if keywords match name.
    t = text.lower()
    candidates = [s for s in stacks if isinstance(s.get("doc"), dict) and (s["doc"].get("intent") or "").lower() == intent]
    # Strong hint: cinematic -> stack name contains cinematic, etc.
    hints = []
    if "cinematic" in t: hints.append("cinematic")
    if "photoreal" in t or "realism" in t: hints.append("real")
    if "lowlight" in t or "night" in t: hints.append("low")
    if hints:
        for h in hints:
            for s in candidates:
                if h in s["name"].lower():
                    return s["name"]
    # Default base stack if present
    base_name = f"{intent}_base"
    for s in candidates:
        if s["name"] == base_name:
            return s["name"]
    return base_name

def choose_presets(stack_doc: Dict[str, Any], text: str) -> List[str]:
    presets = stack_doc.get("presets") or {}
    if not isinstance(presets, dict) or not presets:
        return []
    t = text.lower()
    chosen = []
    # Pick presets whose names appear in text
    for name in presets.keys():
        if name.lower() in t:
            chosen.append(name)
    # Heuristic: lowlight keyword maps to lowlight preset if exists
    if ("lowlight" in t or "night" in t) and "lowlight" in presets and "lowlight" not in chosen:
        chosen.append("lowlight")
    return chosen

def plan(text: str, stacks_dir: str = "stacks") -> Dict[str, Any]:
    intent = infer_intent(text)
    vars = infer_vars(text)
    safe = infer_safety(text)
    count = infer_count(text, default=1)

    stacks_path = Path(stacks_dir).expanduser().resolve()
    stacks = discover_stacks(stacks_path)
    stack_name = choose_stack(stacks, intent, text)

    # Find stack doc for preset inference
    stack_doc = None
    for s in stacks:
        if s["name"] == stack_name:
            stack_doc = s["doc"]
            break
    presets = choose_presets(stack_doc or {}, text)

    # If count>1, encode as batch via a synthetic var if user didn't already provide batches.
    # We'll keep it simple: if user asked for N and no comma vars exist, generate a seed list placeholder
    # (actual engine integration later). For now: expose count to caller.
    out_template = "outputs/{stack}"
    if "mood" in vars: out_template += "/{mood}"
    if "lens" in vars: out_template += "/{lens}"

    return {
        "text": text,
        "stack": stack_name,
        "presets": presets,
        "vars": vars,
        "constraints": {"safe": safe},
        "count": count,
        "out": out_template
    }
