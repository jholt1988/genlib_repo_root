from __future__ import annotations
import requests
from typing import Any

BASE_URL = "https://civitai.com/api/v1/models"


def search_models(
    query: str | None = None,
    model_type: str | None = None,
    base_model: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}

    if query:
        params["query"] = query
    if model_type:
        params["types"] = model_type
    if base_model:
        params["baseModels"] = base_model

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("items", [])
