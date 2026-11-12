import pytest

from claude_aqui import launcher, service
from claude_aqui.base import ConflictError, Context, Status
from claude_aqui.config import load_terminal, save_terminal
from tests.conftest import write_executable


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    monkeypatch.setenv("PATH", str(fakebin))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setattr(launcher, "list_terminals", lambda: ["xterm", "konsole"])
    monkeypatch.setattr(launcher, "resolve_terminal", lambda: "xterm")
    monkeypatch.setattr(launcher, "find_claude", lambda: "/x/claude")
    c = Context(home=home, launcher="/bin/true")
    c.fakebin = fakebin
    return c


def install(ctx, *names):
    for n in names:
        write_executable(ctx.fakebin / n, "exit 0\n")


def rows(ctx):
    return {r.id: r for r in service.snapshot(ctx).managers}


def test_registry_order(ctx):
    assert [m.id for m in service.all_managers(ctx)] == [
        "nautilus", "dolphin", "nemo", "caja", "thunar", "pcmanfm-qt"]


def test_snapshot_marks_conflict_with_message(ctx):
    install(ctx, "nautilus", "caja")
    foreign = ctx.data_dir / "nautilus" / "scripts" / "Abrir Claude Code aqui"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("meu script")
    r = rows(ctx)
    assert r["nautilus"].status is Status.CONFLICT
    assert str(foreign) in r["nautilus"].message
    assert r["caja"].status is Status.DISABLED and r["caja"].message is None
    assert r["dolphin"].status is Status.NOT_INSTALLED and r["dolphin"].message is None


def test_snapshot_flags_terminal_fallback_when_configured_one_missing(ctx):
    save_terminal(ctx, "kitty")
    s = service.snapshot(ctx)
    assert s.configured_terminal == "kitty" and s.terminal_fallback is True
    assert s.effective_terminal == "xterm" and s.terminals == ["xterm", "konsole"]
    save_terminal(ctx, "konsole")
    assert service.snapshot(ctx).terminal_fallback is False
    save_terminal(ctx, None)
    assert service.snapshot(ctx).terminal_fallback is False


def test_snapshot_claude_path_none_when_missing(ctx, monkeypatch):
    monkeypatch.setattr(launcher, "find_claude", lambda: None)
    assert service.snapshot(ctx).claude_path is None


def test_set_manager_roundtrip(ctx):
    install(ctx, "nautilus")
    service.set_manager(ctx, "nautilus", True)
    assert rows(ctx)["nautilus"].status is Status.ENABLED
    service.set_manager(ctx, "nautilus", False)
    assert rows(ctx)["nautilus"].status is Status.DISABLED


def test_set_manager_conflict_leaves_state_unchanged(ctx):
    install(ctx, "nautilus")
    foreign = ctx.data_dir / "nautilus" / "scripts" / "Abrir Claude Code aqui"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("meu script")
    with pytest.raises(ConflictError):
        service.set_manager(ctx, "nautilus", True)
    assert foreign.read_text() == "meu script"
    assert not ctx.stub_path.exists()


def test_remove_all_deletes_every_entry_stub_and_config(ctx):
    install(ctx, "nautilus", "dolphin", "nemo", "caja", "thunar", "pcmanfm-qt")
    for m in service.all_managers(ctx):
        service.set_manager(ctx, m.id, True)
    service.set_terminal(ctx, "xterm")
    other = ctx.data_dir / "nautilus" / "scripts" / "outro"
    other.write_text("alheio")
    # binário some depois de ativar: o entry ainda deve ser removido
    (ctx.fakebin / "nemo").unlink()
    # o uca.xml do Thunar é compartilhado: sobra o arquivo, sem a nossa ação
    entries = [e for m in service.all_managers(ctx) if m.id != "thunar" for e in m.entries()]
    uca = ctx.config_dir / "Thunar" / "uca.xml"
    assert all(e.exists() for e in entries) and "claude-aqui" in uca.read_text()
    service.remove_all(ctx)
    assert not any(e.exists() for e in entries)
    assert "claude-aqui" not in uca.read_text()
    assert not ctx.stub_path.exists() and not ctx.stub_path.parent.exists()
    assert not (ctx.config_dir / "claude-aqui").exists()
    assert other.read_text() == "alheio"
    assert load_terminal(ctx) is None


def test_remove_all_keeps_foreign_files_in_our_dirs(ctx):
    foreign = ctx.config_dir / "claude-aqui" / "notas"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("alheio")
    service.set_terminal(ctx, "xterm")
    service.remove_all(ctx)
    assert foreign.read_text() == "alheio"
    assert not (foreign.parent / "config").exists()


def test_remove_all_keeps_unmarked_stub(ctx):
    ctx.stub_path.parent.mkdir(parents=True)
    ctx.stub_path.write_text("alheio")
    service.remove_all(ctx)
    assert ctx.stub_path.read_text() == "alheio"
