from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

@dataclass
class Plan:
    text: str
    stack: str
    presets: List[str]
    vars: Dict[str, Any]
    constraints: Dict[str, Any]
    out: Optional[str] = None
    count: int = 1
    meta: Optional[Dict[str, Any]] = None

class Planner(Protocol):
    name: str
    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan: ...

def plan_to_dict(p: Plan) -> Dict[str, Any]:
    return {
        "text": p.text,
        "stack": p.stack,
        "presets": p.presets,
        "vars": p.vars,
        "constraints": p.constraints,
        "count": p.count,
        "out": p.out,
        "meta": p.meta or {},
    }
