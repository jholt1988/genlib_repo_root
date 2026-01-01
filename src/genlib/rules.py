from __future__ import annotations
from typing import Any, Dict, List, Tuple

def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]

def compatible(base_asset: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (is_compatible, reasons). Reasons are human-readable."""
    reasons: List[str] = []
    bmd = base_asset.get("metadata") or {}
    cmd = candidate.get("metadata") or {}

    # Base-model match if both specified
    b_base = bmd.get("base_model")
    c_base = cmd.get("base_model")
    if b_base and c_base and b_base != c_base:
        return False, [f"base_model mismatch ({c_base} vs {b_base})"]

    # Explicit avoid lists (either side)
    base_name = bmd.get("name") or base_asset.get("id")
    cand_name = cmd.get("name") or candidate.get("id")

    avoid_with = _as_list(cmd.get("avoid_with"))
    if base_name and base_name in avoid_with:
        return False, [f"candidate avoids base_model '{base_name}'"]

    base_avoid = _as_list(bmd.get("avoid_with"))
    if cand_name and cand_name in base_avoid:
        return False, [f"base_model avoids candidate '{cand_name}'"]

    # Optional: allow lists
    works_best_with = _as_list(cmd.get("works_best_with"))
    if works_best_with and base_name and base_name not in works_best_with:
        reasons.append("not in works_best_with (soft)")

    return True, reasons
