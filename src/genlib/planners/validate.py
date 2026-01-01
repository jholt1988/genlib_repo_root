from __future__ import annotations
from typing import Any, Dict, Tuple
from pathlib import Path

from genlib.stack.cli import resolve_stack
from genlib.stack.schema import validate_stack
from genlib.vars import resolve_vars, VarError
from genlib.presets import load_presets, PresetError
from genlib.utils import load_json

class PlanValidationError(Exception):
    pass

def validate_plan(plan: Dict[str, Any], stacks_dir: str = "stacks") -> Tuple[dict, dict]:
    stacks_path = Path(stacks_dir).expanduser().resolve()
    stack_name = plan.get("stack")
    if not stack_name or not isinstance(stack_name, str):
        raise PlanValidationError("plan.stack missing/invalid")

    # Resolve stack (inheritance)
    doc, chain = resolve_stack(stacks_path, stack_name)
    errs = validate_stack(doc)
    if errs:
        raise PlanValidationError("stack invalid: " + "; ".join(errs))

    # Apply presets -> values
    values = {}
    for pr in plan.get("presets") or []:
        try:
            values.update(load_presets(doc, pr))
        except Exception as e:
            raise PlanValidationError(f"preset '{pr}' invalid: {e}")

    # Apply vars
    pv = plan.get("vars") or {}
    if not isinstance(pv, dict):
        raise PlanValidationError("plan.vars must be object")
    values.update(pv)

    try:
        docs, vars_list = resolve_vars(doc, values)
    except Exception as e:
        raise PlanValidationError(f"vars invalid: {e}")

    # Apply constraints safe default
    constraints = plan.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}
    if "safe" not in constraints:
        constraints["safe"] = True

    # Return a representative resolved doc and vars (batch expansion handled later)
    return docs[0], vars_list[0]
