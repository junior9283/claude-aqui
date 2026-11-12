"""Interface gráfica (GTK4 + libadwaita).

Usa só APIs do libadwaita 1.1 (Ubuntu 22.04), exceto `Adw.Banner` (1.3).
"""
from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import service  # noqa: E402
from .base import ConflictError, Context, Status  # noqa: E402

APP_ID = "br.app.ClaudeAqui"
AUTO_LABEL = "Automático (detectado: {})"
THUNAR_WARNING = "Feche o Thunar antes de ativar; ele pode regravar o arquivo."
_STATUS_SUBTITLE = {
    Status.ENABLED: "Ativado",
    Status.DISABLED: "Desativado",
    Status.NOT_INSTALLED: "Não instalado",
}


class ManagerRowWidget(Adw.ActionRow):
    """Linha com um Gtk.Switch (equivalente ao Adw.SwitchRow, que é 1.4+)."""

    def __init__(self, row: service.ManagerRow):
        super().__init__(title=row.name)
        self.manager_id = row.id
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.add_suffix(self.switch)
        self.set_activatable_widget(self.switch)
        self.update(row)

    def update(self, row: service.ManagerRow) -> None:
        text = row.message if row.status is Status.CONFLICT else _STATUS_SUBTITLE[row.status]
        lines = [GLib.markup_escape_text(text or "Conflito")]
        if row.id == "thunar":
            lines.append(THUNAR_WARNING)
        self.set_subtitle("\n".join(lines))
        self.set_sensitive(row.status is not Status.NOT_INSTALLED)
        self.shown = row.status is Status.ENABLED  # estado real; ignora notificações atrasadas
        self.switch.set_active(self.shown)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, ctx: Context, snapshot_fn):
        super().__init__(application=app, title="Claude Aqui",
                         default_width=520, default_height=640)
        self.ctx = ctx
        self.snapshot_fn = snapshot_fn
        self.manager_rows: dict[str, ManagerRowWidget] = {}
        self.last_toast: Adw.Toast | None = None
        self._terminals: list[str] = []
        self._refreshing = False

        snap = snapshot_fn(ctx)
        page = Adw.PreferencesPage()

        self.banner = Adw.Banner(title="Claude Code não encontrado. Instale-o e reabra este app.")

        managers = Adw.PreferencesGroup(title="Gerenciadores de arquivos")
        for row in snap.managers:
            widget = ManagerRowWidget(row)
            widget.switch.connect("notify::active", self._on_switch, row.id)
            self.manager_rows[row.id] = widget
            managers.add(widget)
        page.add(managers)

        terminal = Adw.PreferencesGroup(title="Terminal")
        self.terminal_row = Adw.ComboRow(title="Terminal")
        self.terminal_row.connect("notify::selected", self._on_terminal)
        terminal.add(self.terminal_row)
        page.add(terminal)

        remove = Adw.PreferencesGroup()
        button = Gtk.Button(label="Remover tudo", halign=Gtk.Align.CENTER)
        button.add_css_class("destructive-action")
        button.connect("clicked", self._on_remove_clicked)
        remove.add(button)
        page.add(remove)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Adw.HeaderBar())
        box.append(self.banner)
        scroller = Gtk.ScrolledWindow(vexpand=True, child=page)
        box.append(scroller)
        self.overlay = Adw.ToastOverlay(child=box)
        self.set_content(self.overlay)
        self._apply(snap)

    # -- estado ---------------------------------------------------------
    def refresh(self) -> None:
        self._apply(self.snapshot_fn(self.ctx))

    def _apply(self, snap: service.AppSnapshot) -> None:
        self._refreshing = True
        try:
            self.banner.set_revealed(snap.claude_path is None)
            for row in snap.managers:
                self.manager_rows[row.id].update(row)
            self._terminals = snap.terminals
            labels = [AUTO_LABEL.format(snap.effective_terminal or "nenhum"), *snap.terminals]
            self.terminal_row.set_model(Gtk.StringList.new(labels))
            if snap.configured_terminal in snap.terminals:
                self.terminal_row.set_selected(snap.terminals.index(snap.configured_terminal) + 1)
            else:
                self.terminal_row.set_selected(0)
            self.terminal_row.set_subtitle(
                f"O terminal escolhido ({snap.configured_terminal}) foi desinstalado; "
                "usando o automático."
                if snap.terminal_fallback else ""
            )
        finally:
            self._refreshing = False

    def toast(self, message: str) -> None:
        self.last_toast = Adw.Toast(title=message)
        self.overlay.add_toast(self.last_toast)

    # -- ações ----------------------------------------------------------
    def _on_switch(self, switch, _pspec, manager_id: str) -> None:
        if switch.get_active() == self.manager_rows[manager_id].shown:
            return
        try:
            service.set_manager(self.ctx, manager_id, switch.get_active())
        except (ConflictError, OSError) as e:
            self.toast(str(e))
        self.refresh()  # sempre reflete o estado real em disco

    def _on_terminal(self, row, _pspec) -> None:
        if self._refreshing:
            return
        index = row.get_selected()
        service.set_terminal(self.ctx, self._terminals[index - 1] if index > 0 else None)

    def _on_remove_clicked(self, _button) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self, heading="Remover tudo?",
            body="Isso remove os itens de menu, o atalho e a configuração criados pelo Claude Aqui.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("remove", "Remover tudo")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_remove_response)
        dialog.present()

    def _on_remove_response(self, _dialog, response: str) -> None:
        if response != "remove":
            return
        service.remove_all(self.ctx)
        self.refresh()
        self.toast("Tudo o que o Claude Aqui criou foi removido.")


def build_window(app, ctx: Context, snapshot_fn=service.snapshot) -> MainWindow:
    return MainWindow(app, ctx, snapshot_fn)


def run() -> int:
    ctx = Context(home=Path.home())
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: build_window(a, ctx).present())
    return app.run(sys.argv[:1])
