"""Núcleo: contexto, gerenciador de arquivos base e stub do menu."""
from __future__ import annotations

import enum
import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

MARKER = "claude-aqui-managed"
DEFAULT_LAUNCHER = "/usr/bin/claude-aqui-launch"


class Status(enum.Enum):
    NOT_INSTALLED = "not_installed"
    DISABLED = "disabled"
    ENABLED = "enabled"
    CONFLICT = "conflict"


class ConflictError(Exception):
    """Um arquivo que não é nosso já ocupa o lugar de um entry."""

    def __init__(self, path: Path):
        super().__init__(f"Já existe um arquivo que não é do Claude Aqui: {path}")
        self.path = path


def atomic_write(path: Path, content: str, mode: int) -> None:
    """Grava via arquivo temporário no mesmo diretório + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def is_managed(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


@dataclass
class Context:
    home: Path
    launcher: str = os.environ.get("CLAUDE_AQUI_LAUNCHER", DEFAULT_LAUNCHER)

    @property
    def data_dir(self) -> Path:
        return Path(os.environ.get("XDG_DATA_HOME") or self.home / ".local/share")

    @property
    def config_dir(self) -> Path:
        return Path(os.environ.get("XDG_CONFIG_HOME") or self.home / ".config")

    @property
    def stub_path(self) -> Path:
        return self.data_dir / "claude-aqui" / "menu-stub"

    def ensure_stub(self) -> Path:
        """Cria/atualiza o stub que os itens de menu chamam."""
        launcher = _sh_quote(self.launcher)
        text = (
            "#!/bin/sh\n"
            f"# {MARKER}\n"
            f"if [ ! -x {launcher} ]; then\n"
            '    notify-send "Claude Aqui" '
            '"O Claude Aqui foi desinstalado; remova este item do menu."\n'
            "    exit 1\n"
            "fi\n"
            f'exec {launcher} "$@"\n'
        )
        atomic_write(self.stub_path, text, 0o755)
        return self.stub_path


class FileManager(ABC):
    id: str
    name: str
    binaries: tuple[str, ...]

    def __init__(self, ctx: Context):
        self.ctx = ctx

    def is_installed(self) -> bool:
        return any(shutil.which(b) for b in self.binaries)

    @abstractmethod
    def entries(self) -> list[Path]:
        """Arquivos que o app cria para este gerenciador."""

    @abstractmethod
    def render(self, entry: Path) -> tuple[str, int]:
        """Conteúdo e modo do entry (deve conter MARKER)."""

    def preserved(self) -> list[Path]:
        """Arquivos do usuário que o disable mantém de propósito (ex.: backups)."""
        return []

    def status(self) -> Status:
        if not self.is_installed():
            return Status.NOT_INSTALLED
        entries = self.entries()
        existing = [e for e in entries if e.exists()]
        if any(not is_managed(e) for e in existing):
            return Status.CONFLICT
        if existing and len(existing) == len(entries):
            return Status.ENABLED
        return Status.DISABLED

    def enable(self) -> None:
        entries = self.entries()
        for entry in entries:
            if entry.exists() and not is_managed(entry):
                raise ConflictError(entry)
        self.ctx.ensure_stub()
        for entry in entries:
            content, mode = self.render(entry)
            atomic_write(entry, content, mode)

    def disable(self) -> None:
        for entry in self.entries():
            if entry.is_file() and is_managed(entry):
                entry.unlink()
