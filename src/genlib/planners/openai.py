from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from genlib.planners.base import Plan

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

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


class OpenAIPlanner:
    name = "openai"

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/responses")

    def plan(self, text: str, *, stacks_dir: str = "stacks") -> Plan:
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY") or os.environ.get("OPENAI_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")

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
            resp = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        content = self._extract_content(data)
        if not content:
            raise RuntimeError("OpenAI response missing text content")

        result = json.loads(content)
        return Plan(
            text=text,
            stack=result.get("stack", "portrait_base"),
            presets=result.get("presets") or [],
            vars=result.get("vars") or {},
            constraints=result.get("constraints") or {"safe": True},
            out=result.get("out"),
            count=int(result.get("count", 1) or 1),
            meta={"planner": "openai", "model": self.model},
        )

    def _extract_content(self, response: Dict[str, Any]) -> str | None:
        out = response.get("output") or []
        for item in out:
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    return c.get("text")
        return None
