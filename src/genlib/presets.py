from __future__ import annotations
from typing import Dict, Any

class PresetError(Exception):
    pass

def load_presets(stack_doc: Dict[str, Any], preset_name: str) -> Dict[str, Any]:
    presets = stack_doc.get("presets") or {}
    if not presets:
        raise PresetError("stack defines no presets")
    if preset_name not in presets:
        raise PresetError(f"unknown preset: {preset_name}")
    vals = presets[preset_name]
    if not isinstance(vals, dict):
        raise PresetError(f"preset '{preset_name}' must be an object")
    return vals
