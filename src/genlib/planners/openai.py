from __future__ import annotations
import json, os
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from genlib.planners.base import Plan

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

def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

class OpenAIPlanner:
    name = "openai"
    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/responses")

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        try:
            resp = _post_json(url, headers, payload)
        except (URLError, HTTPError) as e:
            raise RuntimeError(f"OpenAI request failed: {e}")

        # Responses API returns content in output_text sometimes; fall back to scanning.
        content = None
        try:
            # best-effort extraction
            out = resp.get("output", [])
            for item in out:
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        content = c.get("text")
                        break
        except Exception:
            content = None

        if not content:
            # last-resort: serialize entire resp (user can inspect)
            raise RuntimeError("OpenAI response missing text content")

        data = json.loads(content)
        return Plan(
            text=text,
            stack=data.get("stack", "portrait_base"),
            presets=data.get("presets") or [],
            vars=data.get("vars") or {},
            constraints=data.get("constraints") or {"safe": True},
            out=data.get("out"),
            count=int(data.get("count", 1) or 1),
            meta={"planner": "openai", "model": self.model}
        )
