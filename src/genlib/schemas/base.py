from __future__ import annotations
from typing import Any, Dict, List, Set

# Lightweight validation (no external deps). Fails "soft" by returning errors list.

ALLOWED_TYPES: Set[str] = {"checkpoint", "lora", "tool", "embedding", "controlnet", "upscaler", "unknown"}
ALLOWED_BASE_MODELS: Set[str] = {"SD 1.5", "SDXL", "Flux"}

REQUIRED_BY_TYPE = {
    "checkpoint": {"type", "base_model"},
    "lora": {"type", "base_model"},
}

def validate_metadata(md: Dict[str, Any]) -> List[str]:
    errs: List[str] = []

    if not isinstance(md, dict):
        return ["metadata must be an object"]

    atype = md.get("type")
    if not atype or not isinstance(atype, str):
        return ["missing or invalid field: type"]

    atype_l = atype.lower()
    if atype_l not in ALLOWED_TYPES:
        errs.append(f"unsupported type: {atype}")

    required = REQUIRED_BY_TYPE.get(atype_l, set())
    for f in required:
        if f not in md:
            errs.append(f"missing field: {f}")

    base = md.get("base_model")
    if base is not None:
        if not isinstance(base, str):
            errs.append("base_model must be a string")
        elif base not in ALLOWED_BASE_MODELS:
            errs.append(f"unsupported base_model: {base}")

    nsfw = md.get("nsfw")
    if nsfw is not None and not isinstance(nsfw, bool):
        errs.append("nsfw must be boolean")

    # Weight can be scalar or range string, we validate scalar if present.
    if "weight" in md:
        try:
            w = float(md["weight"])
            if not (0.0 <= w <= 2.0):
                errs.append("weight must be between 0.0 and 2.0")
        except Exception:
            # allow non-numeric; common people put "0.6–1.0"
            pass

    if "default_weight" in md:
        try:
            w = float(md["default_weight"])
            if not (0.0 <= w <= 2.0):
                errs.append("default_weight must be between 0.0 and 2.0")
        except Exception:
            errs.append("default_weight must be numeric")

    # tags/style should be list[str] ideally
    for key in ("tags", "style"):
        if key in md and md[key] is not None:
            v = md[key]
            if isinstance(v, str):
                continue
            if isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
                continue
            errs.append(f"{key} should be a string or list")

    return errs
