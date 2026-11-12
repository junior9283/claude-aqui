import pytest

from claude_aqui import launcher


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake-launch"
    script.write_text(
        '#!/bin/sh\n'
        'case $1 in\n'
        '--list-terminals) printf "kitty\\nxterm\\n" ;;\n'
        '--resolve-terminal) if [ "${2:-}" = --auto ]; then printf "xterm\\n"; else printf "kitty\\n"; fi ;;\n'
        '--find-claude) printf "/home/u/.local/bin/claude\\n" ;;\n'
        'esac\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("CLAUDE_AQUI_LAUNCHER", str(script))
    return script


def test_launcher_client_parses_outputs(fake):
    assert launcher.list_terminals() == ["kitty", "xterm"]
    assert launcher.resolve_terminal() == "kitty"
    assert launcher.resolve_terminal(auto=True) == "xterm"
    assert launcher.find_claude() == "/home/u/.local/bin/claude"


def test_launcher_client_failure_gives_empty(tmp_path, monkeypatch):
    script = tmp_path / "empty"
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    monkeypatch.setenv("CLAUDE_AQUI_LAUNCHER", str(script))
    assert launcher.list_terminals() == []
    assert launcher.resolve_terminal() is None
    assert launcher.find_claude() is None


def test_launcher_client_missing_launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_AQUI_LAUNCHER", str(tmp_path / "nao-existe"))
    assert launcher.list_terminals() == []
    assert launcher.find_claude() is None
