"""PCManFM-Qt: ação libfm (Type=Action) em file-manager/actions."""
from __future__ import annotations

from pathlib import Path

from ..base import MARKER, FileManager
from ._desktop import ACTION_NAME, ICON, exec_line


class PcmanfmManager(FileManager):
    id = "pcmanfm-qt"
    name = "PCManFM-Qt"
    binaries = ("pcmanfm-qt",)

    def entries(self) -> list[Path]:
        return [self.ctx.data_dir / "file-manager/actions/claude-aqui.desktop"]

    def render(self, entry: Path) -> tuple[str, int]:
        text = (
            "[Desktop Entry]\n"
            "Type=Action\n"
            f"Name={ACTION_NAME}\n"
            f"Icon={ICON}\n"
            "Profiles=profile-1;\n"
            f"X-ClaudeAqui={MARKER}\n"
            "\n"
            "[X-Action-Profile profile-1]\n"
            "MimeTypes=inode/directory;\n"
            f"Exec={exec_line(self.ctx.stub_path, '%f')}\n"
        )
        return text, 0o644
