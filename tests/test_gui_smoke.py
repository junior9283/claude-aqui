import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("sem display gráfico", allow_module_level=True)

from claude_aqui import gui  # noqa: E402
from claude_aqui.base import ConflictError, Context, Status  # noqa: E402
from claude_aqui.service import AppSnapshot, ManagerRow  # noqa: E402


def make_snapshot(**over):
    base = dict(
        managers=[
            ManagerRow("nautilus", "Nautilus", Status.ENABLED, None),
            ManagerRow("thunar", "Thunar", Status.DISABLED, None),
            ManagerRow("dolphin", "Dolphin", Status.NOT_INSTALLED, None),
            ManagerRow("nemo", "Nemo", Status.CONFLICT, "Já existe um arquivo: /x"),
        ],
        terminals=["xterm", "konsole"],
        configured_terminal=None,
        effective_terminal="xterm",
        terminal_fallback=False,
        claude_path="/x/claude",
    )
    base.update(over)
    return AppSnapshot(**base)


@pytest.fixture
def ctx(tmp_path):
    return Context(home=tmp_path, launcher="/bin/true")


@pytest.fixture
def build(ctx, monkeypatch):
    Adw.init()
    app = Adw.Application(application_id="br.app.ClaudeAqui.Test")

    def _build(snapshot, **kw):
        monkeypatch.setattr(gui.service, "set_manager", kw.get("set_manager", lambda *a: None))
        monkeypatch.setattr(gui.service, "set_terminal", kw.get("set_terminal", lambda *a: None))
        return gui.build_window(app, ctx, snapshot_fn=lambda c: snapshot)

    return _build


def test_gui_builds_window_from_snapshot(build):
    win = build(make_snapshot())
    assert set(win.manager_rows) == {"nautilus", "thunar", "dolphin", "nemo"}
    assert win.manager_rows["nautilus"].switch.get_active()
    assert not win.manager_rows["thunar"].switch.get_active()
    assert not win.manager_rows["dolphin"].get_sensitive()
    assert "Não instalado" in win.manager_rows["dolphin"].get_subtitle()
    assert "Já existe" in win.manager_rows["nemo"].get_subtitle()
    assert "Feche o Thunar" in win.manager_rows["thunar"].get_subtitle()
    assert not win.banner.get_revealed()
    assert win.terminal_row.get_selected() == 0
    assert win.terminal_row.get_model().get_n_items() == 3


def test_banner_quando_claude_ausente(build):
    win = build(make_snapshot(claude_path=None))
    assert win.banner.get_revealed()


def test_terminal_configurado_e_fallback(build):
    win = build(make_snapshot(configured_terminal="konsole"))
    assert win.terminal_row.get_selected() == 2
    win = build(make_snapshot(configured_terminal="foot", terminal_fallback=True))
    assert win.terminal_row.get_selected() == 0
    assert "desinstalado" in win.terminal_row.get_subtitle()


def test_toggle_chama_servico(build):
    calls = []
    win = build(make_snapshot(), set_manager=lambda c, i, e: calls.append((i, e)))
    win.manager_rows["thunar"].switch.set_active(True)
    assert calls == [("thunar", True)]


def test_conflito_mostra_toast_e_volta_switch(build):
    def boom(ctx, mid, enabled):
        raise ConflictError(ctx.home / "x")

    win = build(make_snapshot(), set_manager=boom)
    win.manager_rows["thunar"].switch.set_active(True)
    assert not win.manager_rows["thunar"].switch.get_active()
    assert win.last_toast is not None and "Já existe" in win.last_toast.get_title()


def test_troca_de_terminal(build):
    calls = []
    win = build(make_snapshot(), set_terminal=lambda c, t: calls.append(t))
    win.terminal_row.set_selected(2)
    win.terminal_row.set_selected(0)
    assert calls == ["konsole", None]
