import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERSION = "9.9.9"


@pytest.fixture(scope="module")
def arch_src():
    subprocess.run(["make", "arch-src", f"VERSION={VERSION}"], cwd=ROOT, check=True, capture_output=True)
    return ROOT / "build" / "arch"


def test_arch_src_gera_pkgbuild_com_versao(arch_src):
    pkgbuild = (arch_src / "PKGBUILD").read_text()
    assert f"pkgver={VERSION}\n" in pkgbuild
    assert "pkgname=claude-aqui" in pkgbuild


def test_tarball_tem_o_nome_esperado_em_source(arch_src):
    pkgbuild = (arch_src / "PKGBUILD").read_text()
    assert 'source=("$pkgname-$pkgver.tar.gz")' in pkgbuild
    assert (arch_src / f"claude-aqui-{VERSION}.tar.gz").is_file()


def test_dependencias_e_sem_scripts_install(arch_src):
    pkgbuild = (arch_src / "PKGBUILD").read_text()
    assert "depends=(python python-gobject gtk4 libadwaita)" in pkgbuild
    assert "libnotify" in pkgbuild
    assert "install=" not in pkgbuild


@pytest.mark.skipif(shutil.which("makepkg") is None, reason="makepkg ausente no host")
def test_makepkg_constroi_pacote(arch_src, tmp_path):
    work = tmp_path / "work"
    shutil.copytree(arch_src, work)
    subprocess.run(["makepkg", "-f", "--nodeps"], cwd=work, check=True, capture_output=True)
    assert list(work.glob("claude-aqui-*.pkg.tar.*"))
