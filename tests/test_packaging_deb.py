import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    shutil.which("dpkg-deb") is None or shutil.which("make") is None,
    reason="dpkg-deb/make ausente",
)

VERSION = "0.1.0"
EXECUTABLES = ("usr/bin/claude-aqui", "usr/bin/claude-aqui-launch")


@pytest.fixture(scope="module")
def deb(tmp_path_factory):
    out = tmp_path_factory.mktemp("deb")
    subprocess.run(
        ["make", "-s", "deb", f"VERSION={VERSION}",
         f"DEBDIR={out / 'root'}", f"DISTDIR={out}"],
        cwd=ROOT, check=True, capture_output=True, text=True)
    return out / f"claude-aqui_{VERSION}_all.deb"


def dpkg(*args):
    return subprocess.run(["dpkg-deb", *args], check=True,
                          capture_output=True, text=True).stdout


def test_control(deb):
    info = dpkg("-I", str(deb))
    assert "Package: claude-aqui" in info
    assert f"Version: {VERSION}" in info
    assert "Architecture: all" in info
    assert "Depends: python3 (>= 3.9), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1" in info
    assert "Recommends: libnotify-bin" in info


def test_no_maintainer_scripts(deb):
    info = dpkg("-I", str(deb))
    for script in ("preinst", "postinst", "prerm", "postrm"):
        assert script not in info


def test_contents(deb):
    lines = dpkg("-c", str(deb)).splitlines()
    paths = {l.split()[-1].removeprefix("./") for l in lines if not l.startswith("d")}
    for p in (*EXECUTABLES,
              "usr/share/applications/claude-aqui.desktop",
              "etc/xdg/autostart/claude-aqui-autoenable.desktop",
              "usr/share/icons/hicolor/scalable/apps/claude-aqui.svg",
              "usr/lib/claude-aqui/claude_aqui/cli.py"):
        assert p in paths, p
    assert not any("__pycache__" in p or p.endswith(".pyc") for p in paths)


def test_modes_and_owner(deb):
    lines = dpkg("-c", str(deb)).splitlines()
    for line in lines:
        assert line.split()[1] == "root/root", line
    for exe in EXECUTABLES:
        line = next(l for l in lines if l.endswith("/" + exe))
        assert line.split()[0] == "-rwxr-xr-x", line


def test_build_with_restrictive_umask(tmp_path):
    """DEBIAN/ precisa de 0755 mesmo com umask 077 (senão o dpkg-deb recusa)."""
    out = tmp_path / "o"
    out.mkdir()
    r = subprocess.run(
        ["sh", "-c", 'umask 077 && make -s deb VERSION=0.0.1 DEBDIR="$1/root" DISTDIR="$1"', "sh", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (out / "claude-aqui_0.0.1_all.deb").is_file()
    assert (out / "root" / "DEBIAN").stat().st_mode & 0o777 == 0o755
