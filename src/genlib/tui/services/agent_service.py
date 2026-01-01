from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class AgentResult:
    ok: bool
    stdout: str
    stderr: str
    code: int


def run_agent_prompt(prompt: str, timeout_sec: int = 120) -> AgentResult:
    '''
    Run the agent pipeline in the most robust way:
      1) Prefer the installed `genlib` CLI (stable interface)
      2) Fall back to a readable error if not available

    This keeps the TUI thin and prevents logic divergence.
    '''
    prompt = (prompt or "").strip()
    if not prompt:
        return AgentResult(False, "", "Prompt is empty.", 2)

    try:
        proc = subprocess.run(
            ["genlib", "agent", "plan", prompt],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return AgentResult(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode)
    except FileNotFoundError:
        return AgentResult(
            False,
            "",
            "genlib CLI not found on PATH. Install editable package (pip install -e .) and retry.",
            127,
        )
    except subprocess.TimeoutExpired:
        return AgentResult(False, "", f"Agent timed out after {timeout_sec}s.", 124)
