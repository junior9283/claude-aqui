"""Thunar: ação personalizada em ~/.config/Thunar/uca.xml."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from claude_aqui.base import ConflictError, FileManager, Status, atomic_write

ID_PREFIX = "claude-aqui-"
ACTION_NAME = "Abrir Claude Code aqui"
BACKUP_SUFFIX = ".claude-aqui.bak"


def _dq(value: str) -> str:
    """Aspas duplas estilo shell (Thunar interpreta o comando com g_shell_parse_argv)."""
    return '"' + "".join("\\" + c if c in '\\"$`' else c for c in value) + '"'


class ThunarManager(FileManager):
    id = "thunar"
    name = "Thunar"
    binaries = ("thunar",)

    @property
    def uca(self) -> Path:
        return self.ctx.config_dir / "Thunar" / "uca.xml"

    @property
    def backup(self) -> Path:
        return self.uca.with_name(self.uca.name + BACKUP_SUFFIX)

    def entries(self) -> list[Path]:
        return [self.uca]

    def render(self, entry: Path) -> tuple[str, int]:
        return ET.tostring(self._build_action(), encoding="unicode"), 0o644

    def _build_action(self) -> ET.Element:
        action = ET.Element("action")
        for tag, text in (
            ("icon", "utilities-terminal"),
            ("name", ACTION_NAME),
            ("unique-id", ID_PREFIX + "1"),
            ("command", f"{_dq(str(self.ctx.stub_path))} %f"),
            ("description", ACTION_NAME),
            ("patterns", "*"),
        ):
            ET.SubElement(action, tag).text = text
        ET.SubElement(action, "directories")
        return action

    def _load(self) -> ET.Element | None:
        """Raiz do uca.xml (None se não existe); malformado -> ConflictError."""
        if not self.uca.exists():
            return None
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        try:
            root = ET.parse(self.uca, parser=parser).getroot()
        except (ET.ParseError, OSError, UnicodeDecodeError) as exc:
            raise ConflictError(self.uca) from exc
        if root.tag != "actions":
            raise ConflictError(self.uca)
        return root

    @staticmethod
    def _ours(root: ET.Element) -> list[ET.Element]:
        return [
            a for a in root.findall("action")
            if (a.findtext("unique-id") or "").strip().startswith(ID_PREFIX)
        ]

    def _save(self, root: ET.Element) -> None:
        if self.uca.exists() and not self.backup.exists():
            shutil.copy2(self.uca, self.backup)
        ET.indent(root, space="  ")
        body = ET.tostring(root, encoding="unicode")
        atomic_write(self.uca, f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n', 0o644)

    def status(self) -> Status:
        if not self.is_installed():
            return Status.NOT_INSTALLED
        try:
            root = self._load()
        except ConflictError:
            return Status.CONFLICT
        return Status.ENABLED if root is not None and self._ours(root) else Status.DISABLED

    def enable(self) -> None:
        root = self._load()
        if root is None:
            root = ET.Element("actions")
        self.ctx.ensure_stub()
        new = self._build_action()
        ours = self._ours(root)
        if len(ours) == 1 and ET.tostring(ours[0]) == ET.tostring(new):
            return
        if ours:  # atualiza no lugar (ex.: o stub mudou de caminho)
            root[list(root).index(ours[0])] = new
            for extra in ours[1:]:
                root.remove(extra)
        else:
            root.append(new)
        self._save(root)

    def disable(self) -> None:
        root = self._load()
        ours = self._ours(root) if root is not None else []
        if not ours:
            return
        for action in ours:
            root.remove(action)
        if len(root) == 0 and not self.backup.exists():
            self.uca.unlink()  # só tinha a nossa ação (e nenhum backup de arquivo alheio)
            return
        self._save(root)
