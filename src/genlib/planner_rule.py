from __future__ import annotations
from typing import Any, Dict
from genlib.planners.base import Plan
from genlib.agents.agent import plan as rule_plan

class RulePlanner:
    name = "rule"
    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan:
        d = rule_plan(text, stacks_dir=stacks_dir)
        return Plan(
            text=text,
            stack=d["stack"],
            presets=d.get("presets") or [],
            vars=d.get("vars") or {},
            constraints=d.get("constraints") or {},
            out=d.get("out"),
            count=int(d.get("count", 1) or 1),
            meta={"planner": "rule"}
        )
