"""Nautilus: item no submenu Scripts (também base do Caja)."""
from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

from claude_aqui.base import MARKER, FileManager, _sh_quote

SCRIPT_NAME = "Abrir Claude Code aqui"


class ScriptManager(FileManager):
    """Gerenciador que só suporta scripts: um executável em uma pasta de scripts."""

    @abstractmethod
    def scripts_dir(self) -> Path:
        """Pasta de scripts do gerenciador."""

    def entries(self) -> list[Path]:
        return [self.scripts_dir() / SCRIPT_NAME]

    def render(self, entry: Path) -> tuple[str, int]:
        # Sem argumentos: o lançador lê as variáveis *_SCRIPT_SELECTED_FILE_PATHS
        # e *_CURRENT_URI do ambiente.
        stub = _sh_quote(str(self.ctx.stub_path))
        return f"#!/bin/sh\n# {MARKER}\nexec {stub}\n", 0o755


class NautilusManager(ScriptManager):
    id = "nautilus"
    name = "Arquivos (Nautilus)"
    binaries = ("nautilus",)

    def scripts_dir(self) -> Path:
        return self.ctx.data_dir / "nautilus" / "scripts"
