from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from genlib.catalog.catalog import build_catalog as _build_catalog_impl


def build_catalog(
    root: Path,
    *,
    include_hash: bool = True,
    validate: bool = True,
    civit_prefetch_limit: int | None = None,
    civit_prefetch_tags: list[str] | None = None,
    civit_prefetch_base: str | None = None,
) -> Dict:
    return _build_catalog_impl(
        root,
        include_hash=include_hash,
        validate=validate,
        civit_prefetch_limit=civit_prefetch_limit,
        civit_prefetch_tags=civit_prefetch_tags,
        civit_prefetch_base=civit_prefetch_base,
    )
