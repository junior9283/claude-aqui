"""Dolphin (KDE): menu de serviço em kio/servicemenus (Plasma 5 e 6)."""
from __future__ import annotations

from pathlib import Path

from ..base import MARKER, FileManager
from ._desktop import ACTION_NAME, ICON, exec_line


class DolphinManager(FileManager):
    id = "dolphin"
    name = "Dolphin"
    binaries = ("dolphin",)

    def entries(self) -> list[Path]:
        return [self.ctx.data_dir / "kio/servicemenus/claude-aqui.desktop"]

    def render(self, entry: Path) -> tuple[str, int]:
        text = (
            "[Desktop Entry]\n"
            "Type=Service\n"
            "Name=Claude Aqui\n"
            "MimeType=inode/directory;\n"
            "Actions=OpenClaude;\n"
            "X-KDE-Priority=TopLevel\n"
            f"X-ClaudeAqui={MARKER}\n"
            "\n"
            "[Desktop Action OpenClaude]\n"
            f"Name={ACTION_NAME}\n"
            f"Icon={ICON}\n"
            f"Exec={exec_line(self.ctx.stub_path, '%f')}\n"
        )
        # Dolphin só confia em menus de serviço executáveis.
        return text, 0o755
