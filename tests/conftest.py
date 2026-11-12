import shutil
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "claude-aqui-launch"

# Utilitários do sistema que o lançador pode usar. O PATH dos testes contém só
# estes (via links simbólicos) e o fakebin, para que terminais, notify-send,
# zenity e claude reais da máquina não interfiram nos resultados.
SYSTEM_TOOLS = ("sh", "bash", "sed", "awk", "head", "tr", "cat", "dirname", "mkdir", "touch", "sleep", "cut", "grep", "env", "mktemp", "rm", "rmdir", "ls")


@pytest.fixture
def launcher_env(tmp_path):
    """Devolve (env, fakebin, log); o PATH do env só enxerga fakebin e sysbin."""
    fakebin = tmp_path / "fakebin"
    sysbin = tmp_path / "sysbin"
    fakebin.mkdir()
    sysbin.mkdir()
    for tool in SYSTEM_TOOLS:
        found = shutil.which(tool, path="/usr/bin:/bin")
        if found:
            (sysbin / tool).symlink_to(found)
    home = tmp_path / "home"
    home.mkdir()
    log = tmp_path / "terminal.log"
    env = {
        "PATH": f"{fakebin}:{sysbin}",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "LANG": "C.UTF-8",
        "CLAUDE_AQUI_ROOT": str(tmp_path / "root"),
    }
    return env, fakebin, log


def write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def make_fake_terminal(fakebin: Path, log: Path, name: str) -> None:
    """Terminal falso: grava o cwd e cada argumento (ARG<...>) em `log`."""
    write_executable(
        fakebin / name,
        f'printf "PWD<%s>\\n" "$PWD" >> "{log}"\n'
        f'for a in "$@"; do printf "ARG<%s>\\n" "$a" >> "{log}"; done\n',
    )


def make_fake_claude(path: Path, log: Path) -> None:
    write_executable(path, f'printf "CLAUDE<%s>\\n" "$PWD" >> "{log}"\n')
