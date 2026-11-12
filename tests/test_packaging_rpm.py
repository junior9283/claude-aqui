import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERSION = "9.8.7"

pytestmark = pytest.mark.skipif(
    shutil.which("rpmbuild") is None or shutil.which("make") is None,
    reason="rpmbuild/make ausente",
)


def rpm_query(rpm: Path, *args):
    return subprocess.run(["rpm", "-qp", *args, str(rpm)], check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def rpm_file(tmp_path_factory):
    out = tmp_path_factory.mktemp("rpm")
    subprocess.run(["make", "-s", "rpm", f"VERSION={VERSION}", f"DISTDIR={out}",
                    f"RPMBUILD_DIR={out / 'rpmbuild'}"],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    rpms = list(out.glob("claude-aqui-*.rpm"))
    assert len(rpms) == 1
    return rpms[0]


def test_lista_de_arquivos(rpm_file):
    listed = set(rpm_query(rpm_file, "-l").split())
    assert {
        "/usr/bin/claude-aqui",
        "/usr/bin/claude-aqui-launch",
        "/usr/share/applications/claude-aqui.desktop",
        "/usr/share/icons/hicolor/scalable/apps/claude-aqui.svg",
        "/usr/lib/claude-aqui/claude_aqui/base.py",
    } <= listed
    assert all(p.startswith(("/usr/bin/", "/usr/lib/claude-aqui", "/usr/share/"))
               for p in listed)
    assert not any("__pycache__" in p for p in listed)


def test_dependencias(rpm_file):
    reqs = rpm_query(rpm_file, "--requires").split()
    for dep in ("python3", "python3-gobject", "gtk4", "libadwaita"):
        assert dep in reqs
    assert "python3 >= 3.9" in " ".join(reqs[i] + " " + reqs[i + 1] + " " + reqs[i + 2]
                                         for i in range(len(reqs) - 2))
    assert "libnotify" in rpm_query(rpm_file, "--recommends")


def test_versao_e_arquitetura(rpm_file):
    out = rpm_query(rpm_file, "--qf", "%{NAME} %{VERSION} %{ARCH}")
    assert out.split() == ["claude-aqui", VERSION, "noarch"]


def test_sem_scripts_de_instalacao(rpm_file):
    assert rpm_query(rpm_file, "--scripts").strip() == ""


def test_ramo_opensuse_usa_typelibs(tmp_path):
    """Leap 16+/Tumbleweed: gtk4/libadwaita viram typelib(Gtk)/typelib(Adw) (sem pacotes gtk4/libadwaita)."""
    out = tmp_path
    subprocess.run(["make", "-s", "rpm", f"VERSION={VERSION}", f"DISTDIR={out}",
                    f"RPMBUILD_DIR={out / 'rpmbuild'}", "RPMBUILD_ARGS=--define 'suse_version 1699'"],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    (rpm,) = out.glob("claude-aqui-*.rpm")
    reqs = rpm_query(rpm, "--requires")
    assert "typelib(Gtk) = 4.0" in reqs and "typelib(Adw) = 1" in reqs
    assert "python3-gobject" in reqs and "python3 >= 3.9" in reqs
    lines = reqs.splitlines()
    assert "gtk4" not in lines and "libadwaita" not in lines


def test_contato_do_mantenedor_unificado():
    spec = (ROOT / "packaging/rpm/claude-aqui.spec").read_text(encoding="utf-8")
    control = (ROOT / "packaging/deb/control.in").read_text(encoding="utf-8")
    assert "Claude Aqui <noreply@example.invalid>" in spec
    assert "Claude Aqui <noreply@example.invalid>" in control
