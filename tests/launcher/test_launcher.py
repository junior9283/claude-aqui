import subprocess

import pytest

from conftest import LAUNCHER, make_fake_claude, make_fake_terminal


def run(env, *args, extra_env=None, stdin="", cwd=None):
    full_env = dict(env)
    full_env.update(extra_env or {})
    return subprocess.run(
        ["/bin/sh", str(LAUNCHER), *args],
        env=full_env,
        input=stdin,
        capture_output=True,
        cwd=cwd,
        text=True,
        timeout=20,
    )


HOSTILE = [
    "a b",
    "a'b\"c",
    "$(touch X)",
    "`touch X`",
    "a;b",
    "a\nb",
    "a\\nb",
    "100%25",
    "%41",
]


@pytest.mark.parametrize("name", HOSTILE, ids=lambda n: repr(n))
def test_hostile_path_arrives_intact(launcher_env, tmp_path, name):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    base = tmp_path / "work"
    base.mkdir()
    folder = base / name
    folder.mkdir()
    r = run(env, str(folder), cwd=base)
    assert r.returncode == 0, r.stderr
    content = log.read_text()
    assert f"ARG<{folder}>\n" in content
    assert content.count("ARG<--run>") == 1
    assert not (base / "X").exists()
    assert not (tmp_path / "X").exists()
    assert not (folder / "X").exists()
    assert not (base.parent / "X").exists()


def test_file_uri_is_decoded(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    folder = tmp_path / "x" / "a b"
    folder.mkdir(parents=True)
    r = run(env, f"file://{tmp_path}/x/a%20b")
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_file_uri_decodes_utf8(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    folder = tmp_path / "ação"
    folder.mkdir()
    r = run(env, f"file://{tmp_path}/a%C3%A7%C3%A3o")
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_nautilus_env_first_selected_path_is_used(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    first = tmp_path / "primeira"
    second = tmp_path / "segunda"
    first.mkdir()
    second.mkdir()
    r = run(env, extra_env={"NAUTILUS_SCRIPT_SELECTED_FILE_PATHS": f"{first}\n{second}\n"})
    assert r.returncode == 0, r.stderr
    content = log.read_text()
    assert f"ARG<{first}>\n" in content
    assert f"ARG<{second}>\n" not in content


def test_caja_env_is_used(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    folder = tmp_path / "caja"
    folder.mkdir()
    r = run(env, extra_env={"CAJA_SCRIPT_SELECTED_FILE_PATHS": f"{folder}\n"})
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_current_uri_used_when_no_selection(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    folder = tmp_path / "atual dir"
    folder.mkdir()
    r = run(
        env,
        extra_env={
            "NAUTILUS_SCRIPT_SELECTED_FILE_PATHS": "",
            "NAUTILUS_SCRIPT_CURRENT_URI": f"file://{tmp_path}/atual%20dir",
        },
    )
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_not_a_directory_shows_error_and_exits_1(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    f = tmp_path / "arquivo.txt"
    f.write_text("x")
    r = run(env, str(f))
    assert r.returncode == 1
    assert "Selecione uma pasta." in r.stderr
    assert not log.exists()


def test_configured_terminal_is_used(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    make_fake_terminal(fakebin, tmp_path / "kitty.log", "kitty")
    cfg = tmp_path / "home" / ".config" / "claude-aqui"
    cfg.mkdir(parents=True)
    (cfg / "config").write_text("# comentário\nterminal=xterm\n")
    folder = tmp_path / "p"
    folder.mkdir()
    assert run(env, "--resolve-terminal").stdout.strip() == "xterm"
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    assert log.exists()
    assert not (tmp_path / "kitty.log").exists()


def test_configured_terminal_uninstalled_falls_back_with_warning(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    cfg = tmp_path / "home" / ".config" / "claude-aqui"
    cfg.mkdir(parents=True)
    (cfg / "config").write_text("terminal=kitty\n")
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    assert "kitty" in r.stderr and "não está instalado" in r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_config_is_never_sourced(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    cfg = tmp_path / "home" / ".config" / "claude-aqui"
    cfg.mkdir(parents=True)
    marker = tmp_path / "pwned"
    (cfg / "config").write_text(f"touch {marker}\nterminal=xterm; touch {marker}\n")
    r = run(env, "--resolve-terminal")
    assert not marker.exists()
    assert r.stdout.strip() == "xterm"


def test_no_terminal_installed_reports_error(launcher_env, tmp_path):
    env, _, _ = launcher_env
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 1
    assert "terminal" in r.stderr.lower()


def test_resolve_order(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
    assert run(env, "--resolve-terminal").stdout.strip() == "kitty"
    make_fake_terminal(fakebin, log, "x-terminal-emulator")
    assert run(env, "--resolve-terminal").stdout.strip() == "x-terminal-emulator"
    make_fake_terminal(fakebin, log, "xdg-terminal-exec")
    assert run(env, "--resolve-terminal").stdout.strip() == "xdg-terminal-exec"


def test_resolve_terminal_none_exits_1(launcher_env):
    env, _, _ = launcher_env
    r = run(env, "--resolve-terminal")
    assert r.returncode == 1
    assert r.stdout == ""


@pytest.mark.parametrize("name", ["xdg-terminal-exec", "x-terminal-emulator"])
def test_generic_launchers_receive_command_as_arguments(launcher_env, tmp_path, name):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, name)
    folder = tmp_path / "a b"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    content = log.read_text()
    assert f"ARG<{folder}>\n" in content
    assert "ARG<--run>\n" in content
    assert f"PWD<{folder}>" in content


def test_list_terminals_only_lists_installed(launcher_env):
    env, fakebin, log = launcher_env
    assert run(env, "--list-terminals").stdout == ""
    make_fake_terminal(fakebin, log, "kitty")
    make_fake_terminal(fakebin, log, "xterm")
    make_fake_terminal(fakebin, log, "x-terminal-emulator")
    r = run(env, "--list-terminals")
    assert r.returncode == 0
    assert r.stdout.split() == ["kitty", "xterm"]


@pytest.mark.parametrize(
    "term,expected",
    [
        ("gnome-terminal", ["--working-directory={d}", "--"]),
        ("konsole", ["--workdir", "{d}", "-e"]),
        ("kitty", ["--directory", "{d}"]),
        ("alacritty", ["--working-directory", "{d}", "-e"]),
        ("xfce4-terminal", ["--working-directory={d}", "-x"]),
        ("xterm", ["-e"]),
    ],
)
def test_terminal_flags(launcher_env, tmp_path, term, expected):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, term)
    folder = tmp_path / "pasta"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    args = [l[4:-1] for l in log.read_text().splitlines() if l.startswith("ARG<")]
    assert args[: len(expected)] == [e.format(d=folder) for e in expected]
    assert args[-2:] == ["--run", str(folder)]
    assert f"PWD<{folder}>" in log.read_text()


def test_find_claude_in_npm_global_outside_path(launcher_env, tmp_path):
    env, _, log = launcher_env
    claude = tmp_path / "home" / ".npm-global" / "bin" / "claude"
    make_fake_claude(claude, log)
    r = run(env, "--find-claude")
    assert r.returncode == 0
    assert r.stdout.strip() == str(claude)


def test_find_claude_missing_exits_1(launcher_env):
    env, _, _ = launcher_env
    r = run(env, "--find-claude")
    assert r.returncode == 1
    assert r.stdout == ""


def test_run_mode_execs_claude_in_folder(launcher_env, tmp_path):
    env, _, log = launcher_env
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    folder = tmp_path / "proj"
    folder.mkdir()
    r = run(env, "--run", str(folder))
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>" in log.read_text()


def test_run_mode_without_claude_prints_message_and_waits_for_key(launcher_env, tmp_path):
    env, _, _ = launcher_env
    folder = tmp_path / "proj"
    folder.mkdir()
    r = run(env, "--run", str(folder), stdin="\n")
    assert "Claude Code" in r.stdout
    assert "não foi encontrado" in r.stdout
    assert r.returncode == 1


def test_run_mode_missing_folder_prints_message(launcher_env, tmp_path):
    env, _, _ = launcher_env
    r = run(env, "--run", str(tmp_path / "nao-existe"), stdin="\n")
    assert "Selecione uma pasta." in r.stdout
    assert r.returncode == 1
