from __future__ import annotations
import argparse, json, shlex, subprocess
from pathlib import Path
from typing import Any, Dict

from genlib.orchestrator import Orchestrator
from genlib.planners.validate import validate_plan, PlanValidationError


def _resolve_text_arg(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("@"):
        path = Path(value[1:]).expanduser()
        if not path.exists():
            raise SystemExit(f"text file not found: {path}")
        return path.read_text(encoding="utf-8")
    return value

def agent_cli(parser: argparse.ArgumentParser):
    sub = parser.add_subparsers(dest="command", required=True)

    o = sub.add_parser("run", help="Multi-agent orchestrated run")
    o.add_argument(
        "--text",
        help="Prompt text or @path/to/file to read the prompt from disk",
    )
    o.add_argument("--stacks-dir", default="stacks")
    o.add_argument("--planners", default="openai,rule,ollama", help="Comma-separated planners (tried in order)")
    o.add_argument("--hybrid-backend", default="openai")
    o.add_argument("--root", default=None)
    o.add_argument("--catalog", default=None)
    o.add_argument("--out", default=None)
    o.add_argument("--engine", default="forge", choices=["none","forge"])
    o.add_argument("--forge-dir", default=None)
    o.add_argument(
        "--stack",
        default=None,
        help="Override the stack that is executed after planning",
    )
    o.add_argument(
        "--script",
        default="genlib stack run {stack}",
        help="Command template used to execute the selected stack (use {stack} placeholder)",
    )
    o.add_argument("--json", action="store_true")
    o.add_argument("--explain", action="store_true")
    o.add_argument("--dry-run", action="store_true")
    o.set_defaults(func=run_cmd)

def run_cmd(args):
    planners = [p.strip() for p in args.planners.split(",") if p.strip()]
    orch = Orchestrator(planners, stacks_dir=args.stacks_dir, hybrid_backend=args.hybrid_backend)
    text = _resolve_text_arg(args.text)
    if not text:
        raise SystemExit("--text is required (use @file to read from disk)")
    trace = orch.run(text)

    plan = trace["selected"]
    if not plan:
        raise SystemExit("No valid plan selected")

    print("# Selected plan")
    print(f"- Stack: {plan['stack']}")
    print(f"- Presets: {', '.join(plan.get('presets') or []) or '(none)'}")
    print(f"- Vars: {json.dumps(plan.get('vars') or {}, indent=2)}")
    print(f"- Outputs: {plan.get('out') or '(default)'}")

    if "{stack}" not in args.script:
        raise SystemExit("--script template must include {stack} placeholder")
    selected_stack = args.stack or plan["stack"]
    script_template = args.script.format(stack=selected_stack)
    cmd = shlex.split(script_template)
    for pr in plan.get("presets") or []:
        cmd += ["--preset", pr]
    for k, v in (plan.get("vars") or {}).items():
        cmd += ["--var", f"{k}={v}"]

    if args.root:
        cmd += ["--root", args.root]
    if args.catalog:
        cmd += ["--catalog", args.catalog]

    out = args.out or plan.get("out")
    if out:
        cmd += ["--out", out]

    if args.dry_run:
        cmd += ["--engine", "none"]
    else:
        cmd += ["--engine", args.engine]
        if args.engine == "forge":
            if not args.forge_dir:
                raise SystemExit("--forge-dir required for forge engine")
            cmd += ["--forge-dir", args.forge_dir]

    if args.json:
        cmd += ["--json"]
    if args.explain:
        cmd += ["--explain"]

    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    if args.explain:
        print("\n# orchestration trace")
        print(json.dumps(trace, indent=2))
