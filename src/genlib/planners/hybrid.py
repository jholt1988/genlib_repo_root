from __future__ import annotations
from typing import Optional
from genlib.planners.base import Plan
from genlib.planner_rule import RulePlanner
from genlib.planners.openai import OpenAIPlanner
from genlib.planners.ollama import OllamaPlanner
from genlib.planners.validate import validate_plan, PlanValidationError

class HybridPlanner:
    name = "hybrid"
    def __init__(self, backend: str = "openai"):
        self.rule = RulePlanner()
        self.backend = backend
        self.openai = OpenAIPlanner()
        self.ollama = OllamaPlanner()

    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan:
        p = self.rule.plan(text, stacks_dir=stacks_dir)
        try:
            validate_plan({
                "stack": p.stack, "presets": p.presets, "vars": p.vars, "constraints": p.constraints, "out": p.out, "count": p.count
            }, stacks_dir=stacks_dir)
            return p
        except Exception:
            # fallback to LLM backend
            if self.backend == "ollama":
                return self.ollama.plan(text, stacks_dir=stacks_dir)
            return self.openai.plan(text, stacks_dir=stacks_dir)
