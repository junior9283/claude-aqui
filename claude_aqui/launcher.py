"""Cliente do lançador (claude-aqui-launch): consulta terminais e o `claude`."""
from __future__ import annotations

import os
import subprocess

from .base import DEFAULT_LAUNCHER


def _run(*args: str) -> list[str]:
    launcher = os.environ.get("CLAUDE_AQUI_LAUNCHER", DEFAULT_LAUNCHER)
    try:
        result = subprocess.run(
            [launcher, *args], capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def list_terminals() -> list[str]:
    return _run("--list-terminals")


def resolve_terminal(auto: bool = False) -> str | None:
    """Terminal efetivo; com auto=True ignora o terminal escolhido na configuração."""
    return next(iter(_run("--resolve-terminal", *(["--auto"] if auto else []))), None)


def find_claude() -> str | None:
    return next(iter(_run("--find-claude")), None)
