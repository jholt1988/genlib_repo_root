from __future__ import annotations
from typing import Any, Dict, List

def validate_stack(doc: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(doc, dict):
        return ["stack file must be a JSON object"]

    if not doc.get("name") or not isinstance(doc.get("name"), str):
        errs.append("missing/invalid field: name")

    if "extends" in doc and doc["extends"] is not None and not isinstance(doc["extends"], str):
        errs.append("extends must be a string (parent stack name)")

    if "intent" in doc and doc["intent"] is not None and not isinstance(doc["intent"], str):
        errs.append("intent must be a string")

    # prompt block
    if "prompt" in doc and doc["prompt"] is not None:
        if not isinstance(doc["prompt"], dict):
            errs.append("prompt must be an object")
        else:
            for k in ("subject", "details", "quality", "negative_add"):
                if k in doc["prompt"] and doc["prompt"][k] is not None and not isinstance(doc["prompt"][k], str):
                    errs.append(f"prompt.{k} must be a string")
            if "style" in doc["prompt"] and doc["prompt"]["style"] is not None:
                st = doc["prompt"]["style"]
                if isinstance(st, str):
                    pass
                elif isinstance(st, list) and all(isinstance(x, str) for x in st):
                    pass
                else:
                    errs.append("prompt.style must be a string or list of strings")

    # constraints block
    if "constraints" in doc and doc["constraints"] is not None:
        if not isinstance(doc["constraints"], dict):
            errs.append("constraints must be an object")
        else:
            if "safe" in doc["constraints"] and doc["constraints"]["safe"] is not None and not isinstance(doc["constraints"]["safe"], bool):
                errs.append("constraints.safe must be boolean")
            if "namespace" in doc["constraints"] and doc["constraints"]["namespace"] is not None and not isinstance(doc["constraints"]["namespace"], str):
                errs.append("constraints.namespace must be a string")

    # selection block
    if "selection" in doc and doc["selection"] is not None:
        if not isinstance(doc["selection"], dict):
            errs.append("selection must be an object")
        else:
            if "max_loras" in doc["selection"] and doc["selection"]["max_loras"] is not None and not isinstance(doc["selection"]["max_loras"], int):
                errs.append("selection.max_loras must be an int")
            for k in ("prefer", "avoid"):
                if k in doc["selection"] and doc["selection"][k] is not None:
                    v = doc["selection"][k]
                    if isinstance(v, str):
                        pass
                    elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                        pass
                    else:
                        errs.append(f"selection.{k} must be a string or list of strings")

    # params block
    if "params" in doc and doc["params"] is not None and not isinstance(doc["params"], dict):
        errs.append("params must be an object")

        if 'vars' in doc and doc['vars'] is not None:
            errs.extend(_validate_vars(doc['vars']))

        if 'presets' in doc and doc['presets'] is not None:
            errs.extend(_validate_presets(doc['presets']))

    return errs


# vars block validation (light)
def _validate_vars(vars_block):
    if not isinstance(vars_block, dict):
        return ["vars must be an object"]
    errs = []
    for k, v in vars_block.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            errs.append(f"invalid var spec: {k}")
        if "default" not in v and not v.get("required"):
            errs.append(f"var '{k}' must have default or required=true")
        if 'vars' in doc and doc['vars'] is not None:
            errs.extend(_validate_vars(doc['vars']))

        if 'presets' in doc and doc['presets'] is not None:
            errs.extend(_validate_presets(doc['presets']))

    return errs


# presets block validation (light)
def _validate_presets(presets):
    if not isinstance(presets, dict):
        return ["presets must be an object"]
    errs = []
    for k, v in presets.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            errs.append(f"invalid preset: {k}")
        if 'presets' in doc and doc['presets'] is not None:
            errs.extend(_validate_presets(doc['presets']))

    return errs
