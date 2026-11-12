import sys

import pytest

from claude_aqui import cli, launcher, service
from claude_aqui.base import Context, Status
from tests.conftest import write_executable


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(fakebin))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setattr(launcher, "list_terminals", lambda: [])
    monkeypatch.setattr(launcher, "resolve_terminal", lambda auto=False: None)
    monkeypatch.setattr(launcher, "find_claude", lambda: None)
    return Context(home=home, launcher="/bin/true"), fakebin


def statuses(ctx):
    return {r.id: r.status for r in service.snapshot(ctx).managers}


def test_cli_enable_all_skips_not_installed(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "nautilus", "exit 0\n")
    write_executable(fakebin / "thunar", "exit 0\n")
    assert cli.main(["--enable", "all"]) == 0
    st = statuses(ctx)
    assert st["nautilus"] is Status.ENABLED and st["thunar"] is Status.ENABLED
    assert st["dolphin"] is Status.NOT_INSTALLED
    assert cli.main(["--disable", "all"]) == 0
    assert statuses(ctx)["nautilus"] is Status.DISABLED


def test_cli_exit_code_on_conflict(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "nautilus", "exit 0\n")
    write_executable(fakebin / "caja", "exit 0\n")
    foreign = ctx.data_dir / "nautilus" / "scripts" / "Abrir Claude Code aqui"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("meu")
    assert cli.main(["--enable", "all"]) == 1
    assert statuses(ctx)["caja"] is Status.ENABLED  # continuou nos demais
    assert foreign.read_text() == "meu"
    assert str(foreign) in capsys.readouterr().err


def test_cli_status_output_lists_each_manager(env, capsys):
    _, fakebin = env
    write_executable(fakebin / "nemo", "exit 0\n")
    assert cli.main(["--status"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split("\t")[0] for ln in lines] == [
        "nautilus", "dolphin", "nemo", "caja", "thunar", "pcmanfm-qt"]
    assert "desativado" in lines[2] and "não instalado" in lines[0]


def test_cli_unknown_and_not_installed_single(env, capsys):
    assert cli.main(["--enable", "xyz"]) == 2
    assert cli.main(["--enable", "nemo"]) == 1


def test_cli_remove_all(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "nautilus", "exit 0\n")
    cli.main(["--enable", "nautilus"])
    assert cli.main(["--remove-all"]) == 0
    assert statuses(ctx)["nautilus"] is Status.DISABLED
    assert not ctx.stub_path.exists()


def test_cli_without_gui_returns_1(env, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "claude_aqui.gui", None)
    assert cli.main([]) == 1
    assert "interface gráfica" in capsys.readouterr().err


def test_cli_without_gui_typelib_returns_1(env, capsys, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "gui" or name.endswith(".gui"):
            raise ValueError("Namespace Gtk not available")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "claude_aqui.gui", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert cli.main([]) == 1
    assert "interface gráfica" in capsys.readouterr().err


def test_cli_disable_works_when_binary_is_gone(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "nemo", "exit 0\n")
    assert cli.main(["--enable", "nemo"]) == 0
    entries = [e for m in service.all_managers(ctx) if m.id == "nemo" for e in m.entries()]
    assert all(e.exists() for e in entries)
    (fakebin / "nemo").unlink()
    assert cli.main(["--disable", "nemo"]) == 0
    assert not any(e.exists() for e in entries)


def test_cli_remove_all_failure_exits_1_and_lists_paths(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "nautilus", "exit 0\n")
    cli.main(["--enable", "nautilus"])
    capsys.readouterr()
    ctx.stub_path.parent.chmod(0o500)
    try:
        code = cli.main(["--remove-all"])
    finally:
        ctx.stub_path.parent.chmod(0o700)
    out = capsys.readouterr()
    assert code == 1
    assert str(ctx.stub_path) in out.err
    assert "foi removido" not in out.out


def test_cli_remove_all_mentions_kept_backup(env, capsys):
    ctx, fakebin = env
    write_executable(fakebin / "thunar", "exit 0\n")
    uca = ctx.config_dir / "Thunar" / "uca.xml"
    uca.parent.mkdir(parents=True)
    uca.write_text("<actions><action><unique-id>u</unique-id></action></actions>")
    cli.main(["--enable", "thunar"])
    capsys.readouterr()
    assert cli.main(["--remove-all"]) == 0
    assert "uca.xml.claude-aqui.bak" in capsys.readouterr().out
