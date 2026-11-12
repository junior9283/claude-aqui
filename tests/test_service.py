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
    monkeypatch.setattr(launcher, "resolve_terminal", lambda auto=False: "xterm" if auto else "konsole")
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
    assert s.auto_terminal == "xterm" and s.terminals == ["xterm", "konsole"]
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
    # o uca.xml do Thunar é compartilhado: a nossa ação sai; o arquivo só sobra se tiver ações de terceiros
    entries = [e for m in service.all_managers(ctx) if m.id != "thunar" for e in m.entries()]
    uca = ctx.config_dir / "Thunar" / "uca.xml"
    assert all(e.exists() for e in entries) and "claude-aqui" in uca.read_text()
    service.remove_all(ctx)
    assert not any(e.exists() for e in entries)
    assert not uca.exists()  # só tinha a nossa ação: o arquivo some junto
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


def test_generated_files_are_never_writable_by_group_or_others(ctx):
    """Segurança: scripts/stub (0755) e configs (0644) só são graváveis pelo dono."""
    install(ctx, "nautilus", "dolphin", "nemo", "caja", "thunar", "pcmanfm-qt")
    for m in service.all_managers(ctx):
        service.set_manager(ctx, m.id, True)
    service.set_terminal(ctx, "xterm")
    files = [f for base in (ctx.data_dir, ctx.config_dir) for f in base.rglob("*") if f.is_file()]
    assert len(files) >= 9
    for path in files:
        assert path.stat().st_mode & 0o022 == 0, path


# ---------- remove_all informa falhas e o que foi mantido (item 12) ----------

def test_remove_all_report_ok_when_everything_removed(ctx):
    install(ctx, "nautilus")
    service.set_manager(ctx, "nautilus", True)
    report = service.remove_all(ctx)
    assert report.ok and report.failed == [] and report.kept == []
    assert report.summary() == "Tudo o que o Claude Aqui criou foi removido."


def test_remove_all_reports_what_could_not_be_removed(ctx):
    install(ctx, "nautilus")
    service.set_manager(ctx, "nautilus", True)
    ctx.stub_path.parent.chmod(0o500)  # sem permissão para apagar o stub
    try:
        report = service.remove_all(ctx)
    finally:
        ctx.stub_path.parent.chmod(0o700)
    assert not report.ok
    assert any(str(ctx.stub_path) in f for f in report.failed)
    assert ctx.stub_path.exists()
    assert "Não foi possível remover" in report.summary()
    assert str(ctx.stub_path) in report.summary()


def test_remove_all_reports_unremovable_entry(ctx):
    install(ctx, "nautilus")
    service.set_manager(ctx, "nautilus", True)
    entry = service.all_managers(ctx)[0].entries()[0]
    entry.parent.chmod(0o500)
    try:
        report = service.remove_all(ctx)
    finally:
        entry.parent.chmod(0o700)
    assert not report.ok and any(str(entry) in f for f in report.failed)


def test_remove_all_reports_malformed_uca_as_not_removed(ctx):
    install(ctx, "thunar")
    uca = ctx.config_dir / "Thunar" / "uca.xml"
    uca.parent.mkdir(parents=True)
    uca.write_text("<actions><action>")
    report = service.remove_all(ctx)
    assert not report.ok and any(str(uca) in f for f in report.failed)
    assert uca.read_text() == "<actions><action>"


def test_remove_all_mentions_kept_user_backup(ctx):
    install(ctx, "thunar")
    uca = ctx.config_dir / "Thunar" / "uca.xml"
    uca.parent.mkdir(parents=True)
    uca.write_text("<actions><action><unique-id>u</unique-id></action></actions>")
    service.set_manager(ctx, "thunar", True)
    report = service.remove_all(ctx)
    bak = uca.with_name("uca.xml.claude-aqui.bak")
    assert bak.exists() and report.ok
    assert report.kept == [bak]
    assert str(bak) in report.summary() and "mantido" in report.summary().lower()
