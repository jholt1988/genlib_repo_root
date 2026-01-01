from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class PromptTemplate:
    name: str
    positive: str
    negative: str

DEFAULT_NEGATIVE = "cartoon, anime, doll, extra fingers, distorted hands, bad anatomy, lowres, blurry, watermark"

TEMPLATES: Dict[str, PromptTemplate] = {
    "portrait": PromptTemplate(
        name="portrait",
        positive=(
            "{quality}, photorealistic portrait of {subject}, {details}, "
            "{style}, natural skin texture, sharp focus, soft shadows"
        ),
        negative=DEFAULT_NEGATIVE + ", deformed face, asymmetrical eyes"
    ),
    "product": PromptTemplate(
        name="product",
        positive=(
            "{quality}, product photo of {subject}, {details}, "
            "{style}, studio lighting, clean background, high contrast"
        ),
        negative=DEFAULT_NEGATIVE + ", cluttered background"
    ),
    "landscape": PromptTemplate(
        name="landscape",
        positive=(
            "{quality}, landscape scene of {subject}, {details}, "
            "{style}, wide angle, atmospheric perspective"
        ),
        negative=DEFAULT_NEGATIVE + ", tilted horizon"
    ),
    "anime": PromptTemplate(
        name="anime",
        positive=(
            "{quality}, anime illustration of {subject}, {details}, "
            "{style}, vibrant colors, clean linework"
        ),
        negative=DEFAULT_NEGATIVE + ", photorealistic"
    ),
}

def render(intent: str, *, subject: str, details: str, style: str, quality: str,
           negative_add: str = "") -> Dict[str, str]:
    t = TEMPLATES.get(intent.lower()) or PromptTemplate(
        name="generic",
        positive="{quality}, {subject}, {details}, {style}",
        negative=DEFAULT_NEGATIVE
    )
    pos = t.positive.format(
        subject=subject or "subject",
        details=details or "",
        style=style or "",
        quality=quality or "high quality"
    ).replace(" ,", ",").strip(" ,")

    neg = t.negative
    if negative_add:
        neg = (neg + ", " + negative_add).strip()

    return {"positive": pos, "negative": neg, "template": t.name}
