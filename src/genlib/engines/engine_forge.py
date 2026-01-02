from __future__ import annotations
from pathlib import Path
import subprocess, json, os
import 
class ForgeError(Exception):
    pass

def run_forge(prompt: str, negative: str, params: dict, outdir: Path, forge_dir: Path, headless: bool = True):
    outdir.mkdir(parents=True, exist_ok=True)

    prompt_file = outdir / "prompt.txt"
    params_file = outdir / "params.json"

    prompt_file.write_text(prompt + "\n\n# negative\n" + negative, encoding="utf-8")
    params_file.write_text(json.dumps(params, indent=2), encoding="utf-8")

    # Build Forge command (non-destructive, uses --skip-install)
    cmd = [
        str(forge_dir / "webui.sh"),
        "--skip-install",
        "--exit-on-success"
    ]

    if headless:
        cmd += ["--nowebui"]

    env = os.environ.copy()
    env["GENLIB_PROMPT_FILE"] = str(prompt_file)
    env["GENLIB_PARAMS_FILE"] = str(params_file)
    env["GENLIB_OUTPUT_DIR"] = str(outdir)

    proc = subprocess.run(cmd, cwd=forge_dir, env=env)
    if proc.returncode != 0:
        raise ForgeError(f"Forge failed with code {proc.returncode}")

def start_forge():
    forge_dir = os.environ.get("FORGE_DIR")
    cmd = [

    ]
