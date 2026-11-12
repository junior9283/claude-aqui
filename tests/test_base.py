import os
import stat
import subprocess
from pathlib import Path

import pytest

from claude_aqui.base import MARKER, ConflictError, Context, FileManager, Status


class FakeManager(FileManager):
    id = "fake"
    name = "Fake"
    binaries = ("fake-fm",)

    def entries(self):
        return [self.ctx.home / "a.desktop", self.ctx.home / "sub" / "b.desktop"]

    def render(self, entry):
        return f"# {MARKER}\nExec={self.ctx.stub_path}\n", 0o644


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    return Context(home=home, launcher=str(tmp_path / "launcher"))


@pytest.fixture
def fm(ctx, tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "fake-fm"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    return FakeManager(ctx)


def test_enable_blocks_foreign_file(fm, ctx):
    foreign = ctx.home / "sub" / "b.desktop"
    foreign.parent.mkdir()
    foreign.write_text("meu arquivo\n")
    with pytest.raises(ConflictError) as exc:
        fm.enable()
    assert exc.value.path == foreign
    assert foreign.read_text() == "meu arquivo\n"
    assert not (ctx.home / "a.desktop").exists()
    assert fm.status() is Status.CONFLICT


def test_disable_never_deletes_foreign_file(fm, ctx):
    foreign = ctx.home / "a.desktop"
    foreign.write_text("meu arquivo\n")
    fm.disable()
    assert foreign.read_text() == "meu arquivo\n"


def test_disable_removes_only_marked_entries(fm, ctx):
    fm.enable()
    foreign = ctx.home / "a.desktop"
    foreign.write_text("trocado\n")
    fm.disable()
    assert foreign.exists()
    assert not (ctx.home / "sub" / "b.desktop").exists()


def test_enable_is_idempotent(fm, ctx):
    fm.enable()
    first = (ctx.home / "a.desktop").read_text()
    fm.enable()
    assert (ctx.home / "a.desktop").read_text() == first
    assert fm.status() is Status.ENABLED


def test_enable_sets_mode_and_leaves_no_temp_files(fm, ctx):
    fm.enable()
    entry = ctx.home / "a.desktop"
    assert stat.S_IMODE(entry.stat().st_mode) == 0o644
    assert sorted(p.name for p in ctx.home.iterdir() if p.is_file()) == ["a.desktop"]
    assert sorted(p.name for p in (ctx.home / "sub").iterdir()) == ["b.desktop"]


def test_status_transitions(fm, monkeypatch):
    assert fm.status() is Status.DISABLED
    fm.enable()
    assert fm.status() is Status.ENABLED
    fm.disable()
    assert fm.status() is Status.DISABLED
    monkeypatch.setenv("PATH", "/nonexistent")
    assert fm.status() is Status.NOT_INSTALLED


def test_context_paths_follow_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    c = Context(home=tmp_path)
    assert c.data_dir == tmp_path / ".local/share"
    assert c.config_dir == tmp_path / ".config"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "c"))
    assert c.data_dir == tmp_path / "d"
    assert c.config_dir == tmp_path / "c"
    assert c.stub_path == tmp_path / "d" / "claude-aqui" / "menu-stub"


def _fake_notify(tmp_path):
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    log = tmp_path / "notify.log"
    nb = bindir / "notify-send"
    nb.write_text(f'#!/bin/sh\nprintf "%s|%s\\n" "$1" "$2" > "{log}"\n')
    nb.chmod(0o755)
    return bindir, log


def test_stub_reports_missing_launcher(ctx, tmp_path):
    bindir, log = _fake_notify(tmp_path)
    stub = ctx.ensure_stub()
    env = {"PATH": f"{bindir}:/usr/bin:/bin"}
    r = subprocess.run([str(stub), "x"], env=env, capture_output=True)
    assert r.returncode == 1
    assert log.read_text() == (
        "Claude Aqui|O Claude Aqui foi desinstalado; remova este item do menu.\n"
    )


def test_stub_execs_launcher_with_args_intact(tmp_path):
    home = tmp_path / "home com espaço"
    home.mkdir()
    out = tmp_path / "out"
    launcher = tmp_path / "lançador 'aspas' $x"
    launcher.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "{out}"\n')
    launcher.chmod(0o755)
    stub = Context(home=home, launcher=str(launcher)).ensure_stub()
    hostile = "/tmp/a b/$(touch pwn); `x` 'q' \"d\""
    assert subprocess.run([str(stub), hostile, "-x"], cwd=tmp_path).returncode == 0
    assert out.read_text() == f"{hostile}\n-x\n"
    assert not (tmp_path / "pwn").exists()


def test_ensure_stub_is_marked_and_executable(ctx):
    stub = ctx.ensure_stub()
    assert MARKER in stub.read_text()
    assert os.access(stub, os.X_OK)
    assert stat.S_IMODE(stub.stat().st_mode) == 0o755
