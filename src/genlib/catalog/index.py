from genlib.catalog.core import ASSET_EXTENSIONS, _category, _stem, _namespace
from genlib.catalog.cache import _resolve_catalog_path
from genlib.schemas.base import validate_metadata



def build_catalog(root: Path, *, include_hash: bool = True, validate: bool = True) -> Dict:
    assets: List[Dict] = []
    for p in root.rglob("*"):
        if not (p.is_file() and p.suffix.lower() in ASSET_EXTENSIONS):
            continue

        meta_path = p.with_suffix(".json")
        md = None
        warnings: List[str] = []

        if meta_path.exists():
            try:
                md = json.loads(meta_path.read_text(encoding="utf-8"))
                if validate:
                    warnings.extend(validate_metadata(md))
            except Exception as e:
                warnings.append(f"invalid_metadata:{e}")
        else:
            warnings.append("missing_metadata")

        aid = _stem(p)
        ns = _namespace(md)
        aref = f"{ns}:{aid}" if ns != "unknown" else aid

        assets.append({
            "id": aid,
            "namespace": ns,
            "ref": aref,
            "filename": p.name,
            "relative_path": str(p.relative_to(root)),
            "category": _category(root, p),
            "type": (md or {}).get("type", "unknown"),
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "sha256": sha256(p) if include_hash else None,
            "metadata": md,
            "warnings": warnings,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "asset_count": len(assets),
        "assets": assets,
    }