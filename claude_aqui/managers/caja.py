"""Caja: item no submenu Scripts."""
from __future__ import annotations

from pathlib import Path

from claude_aqui.managers.nautilus import ScriptManager


class CajaManager(ScriptManager):
    id = "caja"
    name = "Caja"
    binaries = ("caja",)

    def scripts_dir(self) -> Path:
        return self.ctx.config_dir / "caja" / "scripts"
