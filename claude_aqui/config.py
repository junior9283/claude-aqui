"""Configuração do usuário: $XDG_CONFIG_HOME/claude-aqui/config (linhas chave=valor)."""
from __future__ import annotations

import re
from pathlib import Path

from .base import Context, atomic_write

_TERMINAL_LINE = re.compile(r"terminal=([A-Za-z0-9][A-Za-z0-9._+-]*)")


def _config_path(ctx: Context) -> Path:
    return ctx.config_dir / "claude-aqui" / "config"


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def load_terminal(ctx: Context) -> str | None:
    for line in _read_lines(_config_path(ctx)):
        m = _TERMINAL_LINE.fullmatch(line.strip())
        if m:
            return m.group(1)
    return None


def save_terminal(ctx: Context, terminal: str | None) -> None:
    """Grava a escolha (None remove), preservando as demais linhas."""
    path = _config_path(ctx)
    lines = [ln for ln in _read_lines(path) if not ln.strip().startswith("terminal=")]
    if terminal is not None:
        lines.append(f"terminal={terminal}")
    if lines:
        atomic_write(path, "\n".join(lines) + "\n", 0o644)
    else:
        path.unlink(missing_ok=True)
