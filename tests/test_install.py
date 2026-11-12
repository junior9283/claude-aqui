import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make ausente")

EXPECTED = {
    "bin/claude-aqui",
    "bin/claude-aqui-launch",
    "share/applications/claude-aqui.desktop",
    "share/icons/hicolor/scalable/apps/claude-aqui.svg",
}


def make(*args, cwd=ROOT):
    return subprocess.run(["make", "-s", *args], cwd=cwd, check=True,
                          capture_output=True, text=True)


def files(base: Path):
    return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


def test_make_install_layout(tmp_path):
    make("install", f"DESTDIR={tmp_path}", "PREFIX=/usr")
    found = files(tmp_path / "usr")
    assert EXPECTED <= found
    assert "lib/claude-aqui/claude_aqui/cli.py" in found
    assert "lib/claude-aqui/claude_aqui/managers/nautilus.py" in found
    assert not any("__pycache__" in f or f.endswith(".pyc") for f in found)
    assert os.access(tmp_path / "usr/bin/claude-aqui", os.X_OK)
    assert os.access(tmp_path / "usr/bin/claude-aqui-launch", os.X_OK)


def test_installed_launcher_path_is_patched(tmp_path):
    prefix = tmp_path / "opt" / "x y"
    make("install", f"PREFIX={prefix}")
    lib = prefix / "lib/claude-aqui"
    assert f'DEFAULT_LAUNCHER = "{prefix}/bin/claude-aqui-launch"' in (
        lib / "claude_aqui/base.py").read_text()
    assert f'LIB_DIR = "{lib}"' in (prefix / "bin/claude-aqui").read_text()
    # fontes do repositório intocadas
    assert 'DEFAULT_LAUNCHER = "/usr/bin/claude-aqui-launch"' in (
        ROOT / "claude_aqui/base.py").read_text()
    # roda a partir da árvore instalada, sem enxergar o repositório
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(sys.executable)
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": str(bindir), "XDG_CONFIG_HOME": str(home / ".config")}
    r = subprocess.run([str(prefix / "bin/claude-aqui"), "--status"], cwd=tmp_path,
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "nautilus" in r.stdout


def test_make_uninstall_leaves_empty_tree(tmp_path):
    make("install", f"DESTDIR={tmp_path}", "PREFIX=/usr")
    make("uninstall", f"DESTDIR={tmp_path}", "PREFIX=/usr")
    assert files(tmp_path) == set()


def test_make_dist_tarball_contents(tmp_path):
    make("dist", "VERSION=9.9.9", f"DISTDIR={tmp_path}")
    tarball = tmp_path / "claude-aqui-9.9.9.tar.gz"
    assert tarball.is_file()
    with tarfile.open(tarball) as t:
        names = t.getnames()
    assert all(n.split("/")[0] == "claude-aqui-9.9.9" for n in names)
    for need in ("Makefile", "README.md", "bin/claude-aqui", "bin/claude-aqui-launch",
                 "claude_aqui/cli.py", "data/claude-aqui.desktop", "data/claude-aqui.svg"):
        assert f"claude-aqui-9.9.9/{need}" in names
    assert not any(part in n for n in names
                   for part in (".git/", ".venv", ".superpowers", ".claude", "__pycache__"))


@pytest.mark.skipif(shutil.which("desktop-file-validate") is None, reason="sem desktop-file-validate")
def test_desktop_file_valid():
    subprocess.run(["desktop-file-validate", str(ROOT / "data/claude-aqui.desktop")], check=True)
