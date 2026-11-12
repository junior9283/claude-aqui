"""Interface de linha de comando (sem GUI)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import service
from .base import ConflictError, Context, Status

_STATUS_TEXT = {
    Status.NOT_INSTALLED: "não instalado",
    Status.DISABLED: "desativado",
    Status.ENABLED: "ativado",
    Status.CONFLICT: "conflito",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-aqui",
        description="Adiciona 'Abrir Claude Code aqui' aos gerenciadores de arquivos.",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--status", action="store_true", help="mostra o estado de cada gerenciador")
    g.add_argument("--enable", metavar="ID|all", help="ativa o item de menu")
    g.add_argument("--disable", metavar="ID|all", help="desativa o item de menu")
    g.add_argument("--remove-all", action="store_true", help="remove tudo que o app criou")
    return p


def _status(ctx: Context) -> int:
    for row in service.manager_rows(ctx):
        line = f"{row.id}\t{row.name}\t{_STATUS_TEXT[row.status]}"
        print(line + (f"\t{row.message}" if row.message else ""))
    return 0


def _toggle(ctx: Context, target: str, enabled: bool) -> int:
    managers = service.all_managers(ctx)
    if target != "all":
        managers = [m for m in managers if m.id == target]
        if not managers:
            print(f"Gerenciador desconhecido: {target}", file=sys.stderr)
            return 2
    code = 0
    for m in managers:
        if enabled and not m.is_installed():
            if target == "all":
                continue
            print(f"{m.name} não está instalado.", file=sys.stderr)
            return 1
        try:
            service.set_manager(ctx, m.id, enabled)
        except ConflictError as e:
            print(f"{m.name}: {e}", file=sys.stderr)
            code = 1
            continue
        print(f"{m.name}: {'ativado' if enabled else 'desativado'}.")
    return code


def _gui() -> int:
    try:
        from .gui import run
    except (ImportError, ValueError):  # ValueError: typelib do GTK/Adw ausente
        print("A interface gráfica não está disponível; use --status, --enable ou --disable.",
              file=sys.stderr)
        return 1
    return run() or 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ctx = Context(home=Path.home())
    if args.status:
        return _status(ctx)
    if args.enable:
        return _toggle(ctx, args.enable, True)
    if args.disable:
        return _toggle(ctx, args.disable, False)
    if args.remove_all:
        service.remove_all(ctx)
        print("Tudo o que o Claude Aqui criou foi removido.")
        return 0
    return _gui()
