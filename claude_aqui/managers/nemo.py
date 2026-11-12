"""Nemo: ações .nemo_action (pasta selecionada e fundo da pasta)."""
from __future__ import annotations

from pathlib import Path

from ..base import MARKER, FileManager
from ._desktop import ACTION_NAME, ICON, exec_line


class NemoManager(FileManager):
    id = "nemo"
    name = "Nemo"
    binaries = ("nemo",)

    def entries(self) -> list[Path]:
        base = self.ctx.data_dir / "nemo/actions"
        return [base / "claude-aqui.nemo_action", base / "claude-aqui-bg.nemo_action"]

    def render(self, entry: Path) -> tuple[str, int]:
        if entry.name == "claude-aqui-bg.nemo_action":
            # Sem seleção: %P é a pasta aberta no momento.
            selection, extensions, code = "none", "", "%P"
        else:
            selection, extensions, code = "s", "Extensions=dir\n", "%F"
        text = (
            f"# {MARKER}\n"
            "[Nemo Action]\n"
            f"Name={ACTION_NAME}\n"
            f"Icon-Name={ICON}\n"
            f"Exec={exec_line(self.ctx.stub_path, code)}\n"
            f"Selection={selection}\n"
            f"{extensions}"
        )
        return text, 0o644
