from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STACKS_DIR = Path("stacks")
CMF_FILE = Path("genlib.cmf.json")

class ValidationError(Exception):
    pass

def list_cmd(args: Any) -> None:
    if not STACKS_DIR.exists():
        print("No stacks directory found.")
        return

    for p in sorted(STACKS_DIR.glob("*.json")):
        print(p.stem)


def show_cmd(args: Any) -> None:
    path = STACKS_DIR / f"{args.name}.json"
    if not path.exists():
        raise SystemExit(f"Stack not found: {args.name}")

    print(path.read_text())


def build_cmd(args: Any) -> None:
    path = STACKS_DIR / f"{args.name}.json"
    if not path.exists():
        raise SystemExit(f"Stack not found: {args.name}")

    stack = json.loads(path.read_text())
    print(json.dumps(stack, indent=2))


def run_cmd(args: Any) -> None:
    print("Running stack:")
    print(f"  name   = {args.name}")
    print(f"  engine = {args.engine}")

    if args.vars:
        print("  vars:")
        for v in args.vars:
            print(f"    - {v}")

    if args.out:
        print(f"  out    = {args.out}")

    if args.engine == "forge":
        if not args.forge_dir:
            raise SystemExit("--forge-dir is required when engine=forge")
        print(f"  forge  = {args.forge_dir}")

def new_cmd(args: Any) -> None:
    STACKS_DIR.mkdir(exist_ok=True)

    path = STACKS_DIR / f"{args.name}.json"

    if path.exists() and not args.force:
        raise SystemExit(
            f"Stack already exists: {args.name}\n"
            f"Use --force to overwrite."
        )

    stack: dict[str, Any] = {
        "name": args.name,
        "intent": args.name.replace("_", " "),
    }

    if args.extends:
        stack["extends"] = args.extends

    if args.vars:
        vars_block: dict[str, dict[str, str]] = {}
        for v in args.vars:
            if ":" not in v:
                raise SystemExit(
                    f"Invalid --var '{v}'. Expected name:type"
                )
            name, typ = v.split(":", 1)
            vars_block[name] = {"type": typ}
        stack["vars"] = vars_block

    if args.presets:
        stack["presets"] = {p: {} for p in args.presets}

    path.write_text(json.dumps(stack, indent=2) + "\n")

    print(f"✅ Created stack: {path}")




def init_cmd(args: Any) -> None:
    if CMF_FILE.exists() and not args.force:
        raise SystemExit(
            "genlib.cmf.json already exists.\n"
            "Use --force to overwrite."
        )

    # Core directories
    dirs = [
        Path("stacks"),
        Path("outputs"),
        Path("models/checkpoints"),
        Path("models/loras"),
        Path(".genlib"),
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    cmf = {
        "version": "1.0",
        "workspace": Path.cwd().name,
        "defaults": {
            "engine": args.engine,
            "stacks_dir": "stacks",
            "outputs_dir": "outputs",
            "models_dir": "models",
        },
    }

    CMF_FILE.write_text(json.dumps(cmf, indent=2) + "\n")

    print("✅ GenLib workspace initialized")
    print(f"  CMF: {CMF_FILE}")


   


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as e:
        raise ValidationError(f"{path}: invalid JSON ({e})")


def validate_cmf() -> None:
    if not CMF_FILE.exists():
        raise ValidationError("Missing genlib.cmf.json")

    cmf = _load_json(CMF_FILE)

    for key in ("version", "defaults"):
        if key not in cmf:
            raise ValidationError(f"CMF missing key: {key}")

    defaults = cmf["defaults"]
    for key in ("stacks_dir", "outputs_dir", "models_dir"):
        if key not in defaults:
            raise ValidationError(f"CMF.defaults missing key: {key}")

    print("✔ CMF valid")


def validate_stack(path: Path) -> None:
    stack = _load_json(path)

    if "name" not in stack:
        raise ValidationError(f"{path}: missing 'name'")

    if "intent" not in stack:
        raise ValidationError(f"{path}: missing 'intent'")

    if "extends" in stack:
        base = STACKS_DIR / f"{stack['extends']}.json"
        if not base.exists():
            raise ValidationError(
                f"{path}: extends missing stack '{stack['extends']}'"
            )

    if "vars" in stack:
        if not isinstance(stack["vars"], dict):
            raise ValidationError(f"{path}: vars must be an object")

        for name, spec in stack["vars"].items():
            if "type" not in spec:
                raise ValidationError(
                    f"{path}: var '{name}' missing type"
                )

    print(f"✔ Stack valid: {path.name}")


def validate_cmd(args: Any) -> None:
    errors: list[str] = []

    try:
        validate_cmf()
    except ValidationError as e:
        errors.append(str(e))

    if not STACKS_DIR.exists():
        errors.append("Stacks directory missing")
    else:
        if args.name:
            path = STACKS_DIR / f"{args.name}.json"
            if not path.exists():
                errors.append(f"Stack not found: {args.name}")
            else:
                try:
                    validate_stack(path)
                except ValidationError as e:
                    errors.append(str(e))
        else:
            for path in sorted(STACKS_DIR.glob("*.json")):
                try:
                    validate_stack(path)
                except ValidationError as e:
                    errors.append(str(e))

    if errors:
        print("\n❌ Validation failed:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)

    print("\n✅ All validations passed")

    # Placeholder for execution hook
    print("Execution stub (hook engine here)")
