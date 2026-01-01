from __future__ import annotations
from genlib.planner_rule import RulePlanner
from genlib.planners.openai import OpenAIPlanner
from genlib.planners.ollama import OllamaPlanner
from genlib.planners.hybrid import HybridPlanner

def get_planner(name: str, *, hybrid_backend: str = "openai"):
    name = (name or "rule").lower()
    if name == "rule":
        return RulePlanner()
    if name == "openai":
        return OpenAIPlanner()
    if name == "ollama":
        return OllamaPlanner()
    if name == "hybrid":
        return HybridPlanner(backend=hybrid_backend)
    raise ValueError(f"unknown planner: {name}")
