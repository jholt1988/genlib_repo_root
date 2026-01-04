from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests


DEFAULT_FORGE_API_URL = "http://127.0.0.1:7860"


def build_txt2img_payload(
    result: Dict[str, Any],
    *,
    count: int = 1,
    seed: int | None = None,
) -> Dict[str, Any]:
    params = result.get("params") or {}
    steps = int(params.get("steps", 28))
    cfg_scale = float(params.get("cfg_scale", params.get("cfg", 7.0)))
    sampler = params.get("sampler") or params.get("sampler_name") or "Euler a"
    width = int(params.get("width", 512))
    height = int(params.get("height", 512))
    lora_tokens = " ".join(
        f"<lora:{l['forge_id']}:{l['weight']}>" for l in (result.get("loras") or []) if l.get("forge_id")
    )
    positive = result.get("positive_prompt", "")
    prompt = f"{lora_tokens} {positive}".strip() if positive or lora_tokens else ""

    payload = {
        "prompt": prompt,
        "negative_prompt": result.get("negative_prompt", ""),
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler,
        "width": width,
        "height": height,
        "seed": seed,
        "n_iter": count,
        "batch_size": 1,
    }
    return {k: v for k, v in payload.items() if v not in (None, "")}


def invoke_txt2img(
    forge_url: str,
    payload: Dict[str, Any],
    timeout: int = 120,
) -> Dict[str, Any]:
    resp = requests.post(
        f"{forge_url.rstrip('/')}/sdapi/v1/txt2img",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def save_images(
    images: Iterable[str],
    out_dir: Path,
    prefix: str = "image",
) -> List[Path]:
    saved: List[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, encoded in enumerate(images, start=1):
        payload = encoded.split(",", 1)[1] if "," in encoded else encoded
        data = base64.b64decode(payload)
        target = out_dir / f"{prefix}_{idx:02d}.png"
        target.write_bytes(data)
        saved.append(target)
    return saved
