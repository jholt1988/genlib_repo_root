from __future__ import annotations
from typing import Any, Dict, List, Tuple
import re, itertools

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

class VarError(Exception):
    pass

def parse_value(v: Any):
    if isinstance(v, str) and ',' in v:
        return [parse_value(x.strip()) for x in v.split(',')]
    return v

def expand_values(values: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys = []
    options = []
    for k, v in values.items():
        v = parse_value(v)
        if isinstance(v, list):
            keys.append(k)
            options.append(v)
        else:
            keys.append(k)
            options.append([v])
    combos = []
    for prod in itertools.product(*options):
        combos.append(dict(zip(keys, prod)))
    return combos

def resolve_vars(stack: Dict[str, Any], values: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    defs = stack.get("vars") or {}

    expanded = expand_values(values)
    resolved_docs = []
    resolved_vars = []

    for vals in expanded:
        resolved = {}
        for name, spec in defs.items():
            if name in vals:
                val = vals[name]
            elif "default" in spec:
                val = spec.get("default")
            elif spec.get("required"):
                raise VarError(f"missing required var: {name}")
            else:
                val = None

            if val is not None:
                if "choices" in spec and val not in spec["choices"]:
                    raise VarError(f"var '{name}' must be one of {spec['choices']}")
                if isinstance(val, (int, float)):
                    if "min" in spec and val < spec["min"]:
                        raise VarError(f"var '{name}' < min {spec['min']}")
                    if "max" in spec and val > spec["max"]:
                        raise VarError(f"var '{name}' > max {spec['max']}")

            resolved[name] = val

        def subst(obj):
            if isinstance(obj, str):
                def repl(m):
                    k = m.group(1)
                    if k not in resolved:
                        raise VarError(f"unknown var: {k}")
                    return str(resolved[k])
                return VAR_PATTERN.sub(repl, obj)
            if isinstance(obj, list):
                return [subst(x) for x in obj]
            if isinstance(obj, dict):
                return {k: subst(v) for k, v in obj.items() if k != "vars"}
            return obj

        resolved_docs.append(subst(stack))
        resolved_vars.append(resolved)

    return resolved_docs, resolved_vars
