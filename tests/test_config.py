import pytest

from claude_aqui.base import Context
from claude_aqui.config import load_terminal, save_terminal


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return Context(home=tmp_path)


def test_config_roundtrip(ctx):
    assert load_terminal(ctx) is None
    save_terminal(ctx, "kitty")
    assert load_terminal(ctx) == "kitty"
    assert (ctx.config_dir / "claude-aqui" / "config").read_text() == "terminal=kitty\n"


def test_save_none_removes_choice(ctx):
    save_terminal(ctx, "kitty")
    save_terminal(ctx, None)
    assert load_terminal(ctx) is None
    save_terminal(ctx, None)  # sem arquivo: não falha


def test_save_preserves_other_keys(ctx):
    path = ctx.config_dir / "claude-aqui" / "config"
    path.parent.mkdir(parents=True)
    path.write_text("outra=1\nterminal=xterm\n")
    save_terminal(ctx, "konsole")
    assert path.read_text() == "outra=1\nterminal=konsole\n"
    save_terminal(ctx, None)
    assert path.read_text() == "outra=1\n"


def test_config_ignores_malformed_lines(ctx):
    path = ctx.config_dir / "claude-aqui" / "config"
    path.parent.mkdir(parents=True)
    path.write_text("lixo\n# terminal=x\nterminal=\nterminal=a b\nterminal=kitty\n")
    assert load_terminal(ctx) == "kitty"
    path.write_text("lixo\nterminal=\nterminal=../x\n")
    assert load_terminal(ctx) is None
