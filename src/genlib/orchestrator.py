from __future__ import annotations
from typing import Dict, Any, List
import json
from datetime import datetime

from genlib.planners.factory import get_planner
from genlib.planners.validate import validate_plan, PlanValidationError

class OrchestrationError(Exception):
    pass

class Orchestrator:
    def __init__(self, planners: List[str], *, stacks_dir: str = "stacks", hybrid_backend: str = "openai"):
        self.planners = planners
        self.stacks_dir = stacks_dir
        self.hybrid_backend = hybrid_backend

    def run(self, text: str) -> Dict[str, Any]:
        trace = {
            "input": text,
            "timestamp": datetime.utcnow().isoformat(),
            "candidates": [],
            "selected": None,
            "rejected": []
        }

        # 1) Proposers
        for p_name in self.planners:
            planner = get_planner(p_name, hybrid_backend=self.hybrid_backend)
            try:
                plan = planner.plan(text, stacks_dir=self.stacks_dir)
                plan_dict = {
                    "planner": p_name,
                    **{
                        "stack": plan.stack,
                        "presets": plan.presets,
                        "vars": plan.vars,
                        "constraints": plan.constraints,
                        "out": plan.out,
                        "count": plan.count,
                    }
                }
                trace["candidates"].append(plan_dict)
            except Exception as e:
                trace["rejected"].append({"planner": p_name, "reason": str(e)})

        if not trace["candidates"]:
            raise OrchestrationError("No planner produced a candidate")

        # 2) Critic + Validator
        for cand in trace["candidates"]:
            try:
                validate_plan(cand, stacks_dir=self.stacks_dir)
                trace["selected"] = cand
                break
            except PlanValidationError as e:
                trace["rejected"].append({
                    "planner": cand.get("planner"),
                    "reason": f"validation failed: {e}"
                })

        if not trace["selected"]:
            raise OrchestrationError("All plans rejected by validator")

        return trace
