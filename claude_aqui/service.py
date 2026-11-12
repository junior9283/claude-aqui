"""Camada de serviço compartilhada pela GUI e pela CLI."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import launcher
from .base import ConflictError, Context, FileManager, Status, is_managed
from .config import load_terminal, save_terminal
from .managers import all_managers


@dataclass
class ManagerRow:
    id: str
    name: str
    status: Status
    message: str | None


@dataclass
class AppSnapshot:
    managers: list[ManagerRow]
    terminals: list[str]
    configured_terminal: str | None
    auto_terminal: str | None  # o que o modo automático escolheria (ignora a escolha do usuário)
    terminal_fallback: bool  # escolhido não instalado -> usando automático
    claude_path: str | None


def _row(manager: FileManager) -> ManagerRow:
    status = manager.status()
    message = None
    if status is Status.CONFLICT:
        conflicting = next(
            (e for e in manager.entries() if e.exists() and not is_managed(e)), None
        )
        if conflicting is not None:
            message = f"Já existe um arquivo que não é do Claude Aqui: {conflicting}"
    return ManagerRow(manager.id, manager.name, status, message)


def manager_rows(ctx: Context) -> list[ManagerRow]:
    return [_row(m) for m in all_managers(ctx)]


def snapshot(ctx: Context) -> AppSnapshot:
    terminals = launcher.list_terminals()
    configured = load_terminal(ctx)
    return AppSnapshot(
        managers=manager_rows(ctx),
        terminals=terminals,
        configured_terminal=configured,
        auto_terminal=launcher.resolve_terminal(auto=True),
        terminal_fallback=configured is not None and configured not in terminals,
        claude_path=launcher.find_claude(),
    )


def _get_manager(ctx: Context, manager_id: str) -> FileManager:
    for manager in all_managers(ctx):
        if manager.id == manager_id:
            return manager
    raise KeyError(manager_id)


def set_manager(ctx: Context, manager_id: str, enabled: bool) -> None:
    """Liga/desliga um gerenciador; propaga ConflictError ao ligar."""
    manager = _get_manager(ctx, manager_id)
    if enabled:
        manager.enable()
    else:
        manager.disable()


def set_terminal(ctx: Context, terminal: str | None) -> None:
    save_terminal(ctx, terminal)


@dataclass
class RemoveReport:
    failed: list[str] = field(default_factory=list)  # "caminho: motivo" do que não saiu
    kept: list[Path] = field(default_factory=list)  # backups de arquivos do usuário, mantidos de propósito

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        if self.ok:
            lines = ["Tudo o que o Claude Aqui criou foi removido."]
        else:
            lines = ["Não foi possível remover tudo:", *(f"- {f}" for f in self.failed)]
        lines += [f"Mantido de propósito (backup do seu arquivo): {p}" for p in self.kept]
        return "\n".join(lines)


def _failure(path, exc: OSError) -> str:
    return f"{exc.filename or path}: {exc.strerror or exc}"


def remove_all(ctx: Context) -> RemoveReport:
    """Remove tudo que o app criou (entries, stub e configuração) e diz o que ficou."""
    report = RemoveReport()
    managers = all_managers(ctx)
    for manager in managers:
        try:
            manager.disable()
        except ConflictError as exc:
            report.failed.append(f"{exc.path}: arquivo inválido, não foi alterado")
        except OSError as exc:
            report.failed.append(_failure(manager.entries()[0], exc))
    app_config = ctx.config_dir / "claude-aqui"
    # O stub só sai se tiver a nossa marca; o arquivo de config não tem marca,
    # mas o caminho é exclusivamente nosso.
    for path in (ctx.stub_path, app_config / "config"):
        try:
            if path != ctx.stub_path or is_managed(path):
                path.unlink(missing_ok=True)
        except OSError as exc:
            report.failed.append(_failure(path, exc))
    for directory in (ctx.stub_path.parent, app_config):
        try:
            directory.rmdir()
        except OSError:
            pass  # ausente ou com arquivos alheios
    report.kept = [p for m in managers for p in m.preserved()]
    return report
