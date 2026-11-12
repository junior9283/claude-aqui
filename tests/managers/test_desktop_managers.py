import shlex
import shutil
import subprocess
from configparser import ConfigParser
from pathlib import Path

import pytest

from claude_aqui.base import MARKER, ConflictError, Context, Status
from claude_aqui.managers.dolphin import DolphinManager
from claude_aqui.managers.nemo import NemoManager
from claude_aqui.managers.pcmanfm import PcmanfmManager

NAME = "Abrir Claude Code aqui"
ALL = [DolphinManager, NemoManager, PcmanfmManager]
HAS_VALIDATOR = shutil.which("desktop-file-validate") is not None


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    home = tmp_path / "home com espaço"
    home.mkdir()
    # os gerenciadores só contam como instalados se o binário existir
    monkeypatch.setattr("claude_aqui.base.shutil.which", lambda b, *a, **k: f"/usr/bin/{b}")
    return Context(home=home)


def read_ini(path: Path) -> ConfigParser:
    cp = ConfigParser(interpolation=None, delimiters=("=",), comment_prefixes=("#",))
    cp.optionxform = str
    cp.read(path, encoding="utf-8")
    return cp


def check_exec(ctx, line: str, code: str):
    assert shlex.split(line) == [str(ctx.stub_path), code]


def exec_lines(m):
    return [
        line.split("=", 1)[1]
        for e in m.entries()
        for line in e.read_text().splitlines()
        if line.startswith("Exec=")
    ]


# ---------- Dolphin ----------

def test_dolphin_enable_writes_expected_keys(ctx):
    m = DolphinManager(ctx)
    assert (m.id, m.binaries) == ("dolphin", ("dolphin",))
    m.enable()
    f = ctx.data_dir / "kio/servicemenus/claude-aqui.desktop"
    assert m.entries() == [f]
    assert f.stat().st_mode & 0o777 == 0o755
    cp = read_ini(f)
    d = cp["Desktop Entry"]
    assert d["Type"] == "Service"
    assert d["MimeType"] == "inode/directory;"
    assert d["Actions"] == "OpenClaude;"
    assert d["X-KDE-Priority"] == "TopLevel"
    assert d["X-ClaudeAqui"] == MARKER
    a = cp["Desktop Action OpenClaude"]
    assert a["Name"] == NAME
    check_exec(ctx, a["Exec"], "%f")
    assert m.status() is Status.ENABLED


# ---------- Nemo ----------

def test_nemo_enable_writes_expected_keys(ctx):
    m = NemoManager(ctx)
    assert (m.id, m.binaries) == ("nemo", ("nemo",))
    m.enable()
    base = ctx.data_dir / "nemo/actions"
    assert m.entries() == [base / "claude-aqui.nemo_action", base / "claude-aqui-bg.nemo_action"]
    sel = read_ini(base / "claude-aqui.nemo_action")["Nemo Action"]
    assert sel["Name"] == NAME
    assert sel["Selection"] == "s"
    assert sel["Extensions"] == "dir"
    check_exec(ctx, sel["Exec"], "%F")
    for e in m.entries():
        assert "# claude-aqui-managed" in e.read_text()
    assert m.status() is Status.ENABLED


def test_nemo_background_action_uses_selection_none(ctx):
    NemoManager(ctx).enable()
    bg = read_ini(ctx.data_dir / "nemo/actions/claude-aqui-bg.nemo_action")["Nemo Action"]
    assert bg["Selection"] == "none"
    assert "Extensions" not in bg
    check_exec(ctx, bg["Exec"], "%P")


# ---------- PCManFM-Qt ----------

def test_pcmanfm_enable_writes_expected_keys(ctx):
    m = PcmanfmManager(ctx)
    assert (m.id, m.binaries) == ("pcmanfm-qt", ("pcmanfm-qt",))
    m.enable()
    f = ctx.data_dir / "file-manager/actions/claude-aqui.desktop"
    assert m.entries() == [f]
    cp = read_ini(f)
    d = cp["Desktop Entry"]
    assert d["Type"] == "Action"
    assert d["Profiles"] == "profile-1;"
    assert d["Name"] == NAME
    assert d["X-ClaudeAqui"] == MARKER
    p = cp["X-Action-Profile profile-1"]
    assert p["MimeTypes"] == "inode/directory;"
    check_exec(ctx, p["Exec"], "%f")
    assert m.status() is Status.ENABLED


# ---------- Comuns ----------

@pytest.mark.parametrize("cls", ALL)
def test_exec_quotes_stub_path_with_space(cls, ctx):
    m = cls(ctx)
    m.enable()
    assert " " in str(ctx.stub_path)
    lines = exec_lines(m)
    assert lines
    for line in lines:
        assert line.startswith(f'"{ctx.stub_path}" ')
        assert len(shlex.split(line)) == 2
        assert shlex.split(line)[0] == str(ctx.stub_path)


@pytest.mark.parametrize("cls", ALL)
def test_disable_removes_only_ours(cls, ctx):
    m = cls(ctx)
    m.enable()
    other = m.entries()[0].parent / "outro.desktop"
    other.write_text("[Desktop Entry]\nName=Outro\n")
    m.disable()
    assert not any(e.exists() for e in m.entries())
    assert other.exists()
    assert m.status() is Status.DISABLED


@pytest.mark.parametrize("cls", ALL)
def test_foreign_file_conflict(cls, ctx):
    m = cls(ctx)
    foreign = m.entries()[0]
    foreign.parent.mkdir(parents=True)
    foreign.write_text("[Desktop Entry]\nName=Alheio\n")
    assert m.status() is Status.CONFLICT
    with pytest.raises(ConflictError):
        m.enable()
    m.disable()
    assert foreign.read_text() == "[Desktop Entry]\nName=Alheio\n"


@pytest.mark.parametrize("cls", ALL)
def test_not_installed(cls, ctx, monkeypatch):
    monkeypatch.setattr("claude_aqui.base.shutil.which", lambda *a, **k: None)
    assert cls(ctx).status() is Status.NOT_INSTALLED


def test_exec_escapes_special_characters(tmp_path):
    home = tmp_path / 'a "b" $c `d` \\e %f'
    m = DolphinManager(Context(home=home))
    m.enable()
    line = exec_lines(m)[0]
    # desfaz o escape do arquivo (\\ -> \) e depois o do Exec (\x -> x, %% -> %)
    raw = line.replace("\\\\", "\\")
    inner = raw[1 : raw.rindex('" ')]
    out, i = "", 0
    while i < len(inner):
        if inner[i] == "\\":
            i += 1
        out += inner[i]
        i += 1
    assert out.replace("%%", "%") == str(m.ctx.stub_path)


# Tipos/chaves de extensão (KDE e libfm) que o validador do freedesktop não conhece.
KNOWN_EXTENSION_ERRORS = ('is not a registered type value', 'but the type is "Service"', 'key "Profiles"')


@pytest.mark.skipif(not HAS_VALIDATOR, reason="desktop-file-validate ausente")
@pytest.mark.parametrize("cls", [DolphinManager, PcmanfmManager])
def test_desktop_file_validate(cls, ctx):
    m = cls(ctx)
    m.enable()
    for e in m.entries():
        r = subprocess.run(["desktop-file-validate", str(e)], capture_output=True, text=True)
        unexpected = [
            l for l in (r.stdout + r.stderr).splitlines()
            if l.strip() and not any(k in l for k in KNOWN_EXTENSION_ERRORS)
        ]
        assert not unexpected, unexpected
