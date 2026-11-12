"""Registro dos gerenciadores de arquivos suportados."""
from __future__ import annotations

from ..base import Context, FileManager
from .caja import CajaManager
from .dolphin import DolphinManager
from .nautilus import NautilusManager
from .nemo import NemoManager
from .pcmanfm import PcmanfmManager
from .thunar import ThunarManager

_CLASSES = (
    NautilusManager,
    DolphinManager,
    NemoManager,
    CajaManager,
    ThunarManager,
    PcmanfmManager,
)


def all_managers(ctx: Context) -> list[FileManager]:
    return [cls(ctx) for cls in _CLASSES]
