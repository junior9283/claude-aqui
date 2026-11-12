import shlex
import xml.etree.ElementTree as ET

import pytest

from claude_aqui.base import ConflictError, Context, Status
from claude_aqui.managers.thunar import ThunarManager

USER_ACTION = (
    "<action><icon>x</icon><name>Minha ação</name><unique-id>user-1</unique-id>"
    "<command>echo %f</command><patterns>*</patterns><directories/></action>"
)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    return Context(home=home, launcher=str(tmp_path / "launcher"))


@pytest.fixture
def mgr(ctx, tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "thunar"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    return ThunarManager(ctx)


@pytest.fixture
def uca(ctx):
    return ctx.config_dir / "Thunar" / "uca.xml"


def write_uca(uca, body):
    uca.parent.mkdir(parents=True, exist_ok=True)
    uca.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<actions>{body}</actions>\n', encoding="utf-8")


def ids(uca):
    return [a.findtext("unique-id") for a in ET.parse(uca).getroot().findall("action")]


def test_creates_uca_when_missing(mgr, uca):
    assert mgr.status() is Status.DISABLED
    mgr.enable()
    root = ET.parse(uca).getroot()
    assert root.tag == "actions"
    (action,) = root.findall("action")
    assert action.findtext("unique-id") == "claude-aqui-1"
    assert action.findtext("name") == "Abrir Claude Code aqui"
    assert action.findtext("patterns") == "*"
    assert action.find("directories") is not None
    assert mgr.status() is Status.ENABLED
    assert not uca.with_name("uca.xml.claude-aqui.bak").exists()
    assert mgr.ctx.stub_path.exists()


def test_not_installed(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert ThunarManager(ctx).status() is Status.NOT_INSTALLED


def test_preserves_user_actions_and_order(mgr, uca):
    second = USER_ACTION.replace("user-1", "user-2").replace("Minha ação", "Outra")
    write_uca(uca, USER_ACTION + second)
    mgr.enable()
    assert ids(uca) == ["user-1", "user-2", "claude-aqui-1"]
    assert ET.parse(uca).getroot().findall("action")[0].findtext("name") == "Minha ação"


def test_enable_twice_does_not_duplicate(mgr, uca):
    mgr.enable()
    mgr.enable()
    assert ids(uca) == ["claude-aqui-1"]


def test_disable_removes_only_ours_and_keeps_user_actions(mgr, uca):
    write_uca(uca, USER_ACTION)
    mgr.enable()
    mgr.disable()
    assert ids(uca) == ["user-1"]
    assert mgr.status() is Status.DISABLED


def test_disable_without_file_is_noop(mgr, uca):
    mgr.disable()
    assert not uca.exists()


def test_malformed_xml_raises_conflict_and_file_untouched(mgr, uca):
    uca.parent.mkdir(parents=True)
    uca.write_text("<actions><action>", encoding="utf-8")
    assert mgr.status() is Status.CONFLICT
    with pytest.raises(ConflictError) as exc:
        mgr.enable()
    assert exc.value.path == uca
    assert uca.read_text(encoding="utf-8") == "<actions><action>"
    assert not uca.with_name("uca.xml.claude-aqui.bak").exists()


def test_backup_created_before_first_edit(mgr, uca):
    write_uca(uca, USER_ACTION)
    original = uca.read_text(encoding="utf-8")
    bak = uca.with_name("uca.xml.claude-aqui.bak")
    mgr.enable()
    assert bak.read_text(encoding="utf-8") == original
    mgr.disable()
    mgr.enable()
    assert bak.read_text(encoding="utf-8") == original  # não sobrescreve


def test_command_quotes_stub_with_space(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    home = tmp_path / "minha casa"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "thunar").write_text("#!/bin/sh\n")
    (bindir / "thunar").chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    m = ThunarManager(Context(home=home, launcher="/x"))
    m.enable()
    command = ET.parse(m.entries()[0]).getroot().findtext("action/command")
    assert shlex.split(command) == [str(m.ctx.stub_path), "%f"]
