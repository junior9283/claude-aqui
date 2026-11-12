import os
import stat
import subprocess

import pytest

from claude_aqui.base import MARKER, ConflictError, Context, Status
from claude_aqui.managers.caja import CajaManager
from claude_aqui.managers.nautilus import NautilusManager

CASES = [
    pytest.param(NautilusManager, "NAUTILUS", ".local/share/nautilus/scripts", id="nautilus"),
    pytest.param(CajaManager, "CAJA", ".config/caja/scripts", id="caja"),
]
NAME = "Abrir Claude Code aqui"


@pytest.fixture(autouse=True)
def _xdg_limpo(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _manager(cls, home, monkeypatch, launcher="/bin/true"):
    mgr = cls(Context(home, launcher=str(launcher)))
    monkeypatch.setattr(mgr, "is_installed", lambda: True)
    return mgr


def test_metadata():
    assert (NautilusManager.id, NautilusManager.name, NautilusManager.binaries) == (
        "nautilus", "Arquivos (Nautilus)", ("nautilus",))
    assert (CajaManager.id, CajaManager.name, CajaManager.binaries) == ("caja", "Caja", ("caja",))


@pytest.mark.parametrize("cls,var,rel", CASES)
def test_entry_path(cls, var, rel, tmp_path, monkeypatch):
    mgr = _manager(cls, tmp_path, monkeypatch)
    assert mgr.entries() == [tmp_path / rel / NAME]


@pytest.mark.parametrize("cls,var,rel", CASES)
def test_enable_creates_executable_script(cls, var, rel, tmp_path, monkeypatch):
    mgr = _manager(cls, tmp_path, monkeypatch)
    mgr.enable()
    script = tmp_path / rel / NAME
    assert stat.S_IMODE(script.stat().st_mode) == 0o755
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert MARKER in text
    assert str(mgr.ctx.stub_path) in text
    assert mgr.status() is Status.ENABLED


@pytest.mark.parametrize("cls,var,rel", CASES)
def test_script_works_with_home_containing_space(cls, var, rel, tmp_path, monkeypatch):
    home = tmp_path / "meu home"
    home.mkdir()
    log = tmp_path / "launcher.log"
    fake = tmp_path / "fake-launcher"
    fake.write_text(
        f'#!/bin/sh\n{{ echo "args=$#"; echo "sel=${var}_SCRIPT_SELECTED_FILE_PATHS"; }} > "{log}"\n'
    )
    fake.chmod(0o755)
    folder = tmp_path / "projeto"
    folder.mkdir()

    mgr = _manager(cls, home, monkeypatch, launcher=fake)
    mgr.enable()
    env = {**os.environ, f"{var}_SCRIPT_SELECTED_FILE_PATHS": f"{folder}\n"}
    subprocess.run([str(home / rel / NAME)], env=env, check=True)

    out = log.read_text(encoding="utf-8")
    assert "args=0" in out
    assert f"sel={folder}" in out


@pytest.mark.parametrize("cls,var,rel", CASES)
def test_disable_removes_script(cls, var, rel, tmp_path, monkeypatch):
    mgr = _manager(cls, tmp_path, monkeypatch)
    mgr.enable()
    mgr.disable()
    assert not (tmp_path / rel / NAME).exists()
    assert mgr.status() is Status.DISABLED


@pytest.mark.parametrize("cls,var,rel", CASES)
def test_foreign_script_conflict(cls, var, rel, tmp_path, monkeypatch):
    mgr = _manager(cls, tmp_path, monkeypatch)
    script = tmp_path / rel / NAME
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\necho meu\n")
    assert mgr.status() is Status.CONFLICT
    with pytest.raises(ConflictError):
        mgr.enable()
    assert script.read_text() == "#!/bin/sh\necho meu\n"
