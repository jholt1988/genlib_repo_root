from __future__ import annotations
import json, os
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from genlib.planners.base import Plan
from genlib.stack.run import suggest_models_for_stack

SYSTEM = """You are a planning assistant for a CLI that runs Stable Diffusion Forge via reusable stack files.
Return ONLY valid JSON matching this schema:
{
  "stack": string,
  "presets": [string],
  "vars": object,
  "constraints": object,
  "out": string|null,
  "count": integer
}
Rules:
- Prefer using existing stacks like portrait_base/product_base/landscape_base/anime_base when unsure.
- vars may include subject, mood (cinematic|soft|dramatic), lens (e.g. 50mm), and any other stack-defined vars.
- constraints.safe should be true unless user explicitly requests NSFW.
- If user requests multiple lenses or moods, use comma-separated values in vars to enable batching.
"""

def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

class OllamaPlanner:
    name = "ollama"
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan:
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
            "stream": False
        }
        try:
            resp = _post_json(url, payload)
        except (URLError, HTTPError) as e:
            raise RuntimeError(f"Ollama request failed: {e}")

        content = None
        try:
            content = resp["message"]["content"]
        except Exception:
            pass
        if not content:
            raise RuntimeError("Ollama response missing message.content")

        data = json.loads(content)
        stack = data.get("stack", "portrait_base")
        model_suggestions = None
        model_suggestion_error: str | None = None
        try:
            model_suggestions = suggest_models_for_stack(
                stack,
                stacks_dir=stacks_dir,
                presets=data.get("presets") or [],
                vars=data.get("vars") or {},
            )
        except Exception as exc:
            model_suggestion_error = str(exc)
        return Plan(
            text=text,
            stack=stack,
            presets=data.get("presets") or [],
            vars=data.get("vars") or {},
            constraints=data.get("constraints") or {"safe": True},
            out=data.get("out"),
            count=int(data.get("count", 1) or 1),
            meta={
                "planner": "ollama",
                "model": self.model,
                "host": self.host,
                **({"model_suggestions": model_suggestions} if model_suggestions else {}),
                **({"model_suggestion_error": model_suggestion_error} if model_suggestion_error else {}),
            }
        )
