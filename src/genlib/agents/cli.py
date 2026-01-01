from __future__ import annotations
import argparse, json, subprocess
from typing import Any, Dict

from genlib.orchestrator import Orchestrator
from genlib.planners.validate import validate_plan, PlanValidationError

def agent_cli(parser: argparse.ArgumentParser):
    sub = parser.add_subparsers(dest="command", required=True)

    o = sub.add_parser("run", help="Multi-agent orchestrated run")
    o.add_argument("--text")
    o.add_argument("--stacks-dir", default="stacks")
    o.add_argument("--planners", default="rule,openai,ollama", help="Comma list of planners")
    o.add_argument("--hybrid-backend", default="openai")
    o.add_argument("--root", default=None)
    o.add_argument("--catalog", default=None)
    o.add_argument("--out", default=None)
    o.add_argument("--engine", default="forge", choices=["none","forge"])
    o.add_argument("--forge-dir", default=None)
    o.add_argument("--json", action="store_true")
    o.add_argument("--explain", action="store_true")
    o.add_argument("--dry-run", action="store_true")
    o.set_defaults(func=run_cmd)

def run_cmd(args):
    planners = [p.strip() for p in args.planners.split(",") if p.strip()]
    orch = Orchestrator(planners, stacks_dir=args.stacks_dir, hybrid_backend=args.hybrid_backend)
    trace = orch.run(args.text)

    plan = trace["selected"]
    if not plan:
        raise SystemExit("No valid plan selected")

    # Build stack run command
    cmd = ["genlib", "stack", "run", plan["stack"]]
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
