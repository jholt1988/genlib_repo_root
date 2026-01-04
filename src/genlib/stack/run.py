from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from genlib.catalog.utils import ensure_catalog
from genlib.compose import compose_from_stack
from genlib.presets import load_presets, PresetError
from genlib.stack.cli import resolve_stack
from genlib.stack.schema import validate_stack
from genlib.utils import DEFAULT_FORGE_MODELS_DIR, env_default
from genlib.vars import resolve_vars, VarError


def resolve_stack_document(
    stack_name: str,
    stacks_dir: str = "stacks",
    *,
    presets: Sequence[str] | None = None,
    vars: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Resolve a stack definition after applying presets and variable overrides.
    Raises RuntimeError if the stack, presets, or vars are invalid.
    """
    if not stack_name:
        raise RuntimeError("stack name is required")

    stacks_path = Path(stacks_dir).expanduser().resolve()
    doc, _ = resolve_stack(stacks_path, stack_name)
    errs = validate_stack(doc)
    if errs:
        raise RuntimeError("stack invalid: " + "; ".join(errs))

    values: Dict[str, Any] = {}
    for preset in (presets or []):
        try:
            values.update(load_presets(doc, preset))
        except PresetError as exc:
            raise RuntimeError(f"preset '{preset}' invalid: {exc}") from exc

    vars_block = dict(vars or {})
    values.update(vars_block)

    try:
        resolved_docs, _ = resolve_vars(doc, values)
    except VarError as exc:
        raise RuntimeError(f"vars invalid: {exc}") from exc
    return resolved_docs[0]


def suggest_models_for_stack(
    stack_name: str,
    *,
    stacks_dir: str = "stacks",
    presets: Sequence[str] | None = None,
    vars: Mapping[str, Any] | None = None,
    models_root: str | None = None,
    catalog_path: str | None = None,
) -> Dict[str, Any] | None:
    """
    Compose the resolved stack against the local catalog to surface a base model
    plus compatible LoRAs. Returns None if the necessary model catalog is missing
    or composition fails.
    """
    resolved_doc = resolve_stack_document(stack_name, stacks_dir=stacks_dir, presets=presets, vars=vars)
    models_root_path = Path(models_root or env_default("GENLIB_MODELS_DIR", DEFAULT_FORGE_MODELS_DIR)).expanduser().resolve()
    catalog_file, _ = ensure_catalog(models_root_path, catalog_path)
    result = compose_from_stack(
        resolved_doc,
        models_root=str(models_root_path),
        catalog_path=str(catalog_file),
        explain=False,
    )
    return {
        "base_model": result.get("base_model"),
        "base_ref": result.get("base_ref"),
        "loras": result.get("loras") or [],
    }
