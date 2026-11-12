import subprocess

import pytest

from conftest import LAUNCHER, make_fake_claude, make_fake_terminal, write_executable


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
    "-rf",
]


@pytest.mark.parametrize("name", HOSTILE, ids=lambda n: repr(n))
def test_hostile_path_arrives_intact(launcher_env, tmp_path, name):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
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
    make_fake_terminal(fakebin, log, "kitty")
    folder = tmp_path / "x" / "a b"
    folder.mkdir(parents=True)
    r = run(env, f"file://{tmp_path}/x/a%20b")
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


@pytest.mark.parametrize("encoded,name", [("100%2525", "100%25"), ("%2541", "%41"), ("%41", "A")])
def test_file_uri_percent_edge_cases(launcher_env, tmp_path, encoded, name):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
    folder = tmp_path / name
    folder.mkdir()
    r = run(env, f"file://{tmp_path}/{encoded}")
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_file_uri_decodes_utf8(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
    folder = tmp_path / "ação"
    folder.mkdir()
    r = run(env, f"file://{tmp_path}/a%C3%A7%C3%A3o")
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_nautilus_env_first_selected_path_is_used(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
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
    make_fake_terminal(fakebin, log, "kitty")
    folder = tmp_path / "caja"
    folder.mkdir()
    r = run(env, extra_env={"CAJA_SCRIPT_SELECTED_FILE_PATHS": f"{folder}\n"})
    assert r.returncode == 0, r.stderr
    assert f"ARG<{folder}>\n" in log.read_text()


def test_current_uri_used_when_no_selection(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
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
    make_fake_terminal(fakebin, log, "kitty")
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
    make_fake_terminal(fakebin, log, "alacritty")
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
    assert "ARG<--run>\n" in content
    assert f"ARG<{folder}>" not in content
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
    if term == "xterm":  # sem flags de lista confiáveis: o caminho não vai no argv
        assert args[-1] == "--run" and str(folder) not in args
    else:
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


def make_fake_desktop_tool(fakebin, name, output):
    write_executable(fakebin / name, f"printf '%s\\n' \"{output}\"\n")


def test_desktop_gsettings_terminal_before_known_list(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "gnome-terminal")
    make_fake_terminal(fakebin, log, "kitty")
    make_fake_desktop_tool(fakebin, "gsettings", "'kitty'")
    assert run(env, "--resolve-terminal").stdout.strip() == "kitty"


def test_desktop_kreadconfig_terminal(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "gnome-terminal")
    make_fake_terminal(fakebin, log, "alacritty")
    make_fake_desktop_tool(fakebin, "kreadconfig6", "/usr/bin/alacritty")
    assert run(env, "--resolve-terminal").stdout.strip() == "alacritty"


def test_desktop_terminal_ignored_when_unknown_or_missing(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "konsole")
    make_fake_desktop_tool(fakebin, "gsettings", "'kitty'")  # não instalado
    assert run(env, "--resolve-terminal").stdout.strip() == "konsole"
    make_fake_desktop_tool(fakebin, "gsettings", "'rm -rf'")  # desconhecido
    assert run(env, "--resolve-terminal").stdout.strip() == "konsole"


def test_desktop_terminal_comes_after_generic_launchers(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
    make_fake_terminal(fakebin, log, "x-terminal-emulator")
    make_fake_desktop_tool(fakebin, "gsettings", "'kitty'")
    assert run(env, "--resolve-terminal").stdout.strip() == "x-terminal-emulator"


def test_find_claude_in_usr_bin_with_lean_path(launcher_env, tmp_path):
    env, _, log = launcher_env
    claude = tmp_path / "root" / "usr" / "bin" / "claude"
    make_fake_claude(claude, log)
    r = run(env, "--find-claude")
    assert r.stdout.strip() == str(claude)


@pytest.mark.parametrize("name", HOSTILE, ids=lambda n: repr(n))
def test_run_mode_hostile_path(launcher_env, tmp_path, name):
    env, _, log = launcher_env
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    base = tmp_path / "work"
    base.mkdir()
    folder = base / name
    folder.mkdir()
    r = run(env, "--run", str(folder), cwd=base)
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>\n" in log.read_text()
    assert not (base / "X").exists()


def test_run_mode_without_argument_uses_inherited_cwd(launcher_env, tmp_path):
    env, _, log = launcher_env
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    folder = tmp_path / "herdado"
    folder.mkdir()
    r = run(env, "--run", cwd=folder)
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>\n" in log.read_text()


@pytest.mark.parametrize("term", ["x-terminal-emulator", "xterm", "xdg-terminal-exec"])
@pytest.mark.parametrize("name", HOSTILE, ids=lambda n: repr(n))
def test_string_joining_terminal_cannot_reinterpret_path(launcher_env, tmp_path, term, name):
    """Terminal que junta o argv numa string e roda via sh -c: o caminho não pode ir no argv."""
    env, fakebin, log = launcher_env
    # cópia do lançador em caminho sem espaços (o sh -c do terminal falso racha em espaços)
    safe_bin = tmp_path / "safebin"
    safe_bin.mkdir()
    launcher = safe_bin / "claude-aqui-launch"
    launcher.write_bytes(LAUNCHER.read_bytes())
    launcher.chmod(0o755)
    skip_e = '[ "$1" = "-e" ] && shift\n'
    write_executable(fakebin / term, skip_e + 'sh -c "$*"\n')
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    base = tmp_path / "work"
    base.mkdir()
    folder = base / name
    folder.mkdir()
    r = subprocess.run(
        ["/bin/sh", str(launcher), str(folder)],
        env=env, cwd=base, capture_output=True, text=True, timeout=20,
    )
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>\n" in log.read_text()
    assert not (base / "X").exists()
    assert not (folder / "X").exists()


# ---------- terminal que falha ao abrir (item 2) ----------

def test_terminal_that_exits_1_without_running_inner_reports_error(launcher_env, tmp_path):
    env, fakebin, _ = launcher_env
    write_executable(fakebin / "kitty", "exit 1\n")
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 1
    assert "kitty" in r.stderr and "terminal" in r.stderr.lower()


def test_terminal_that_runs_inner_and_then_exits_1_is_not_a_launcher_error(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    # terminal falso: roda o modo interno (que cria o marcador) e depois sai com 1
    write_executable(
        fakebin / "kitty",
        f'while [ "$1" != "--run" ]; do shift; done; /bin/sh "{LAUNCHER}" "$@"; exit 1\n',
    )
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""
    assert f"CLAUDE<{folder}>" in log.read_text()


def test_daemonizing_terminal_returning_0_fast_is_not_an_error(launcher_env, tmp_path):
    env, fakebin, _ = launcher_env
    write_executable(fakebin / "kitty", "exit 0\n")
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0 and r.stderr == ""


def test_state_dir_is_cleaned_up(launcher_env, tmp_path):
    env, fakebin, _ = launcher_env
    tmp = tmp_path / "tmpdir"
    tmp.mkdir()
    write_executable(fakebin / "kitty", "exit 1\n")
    folder = tmp_path / "p"
    folder.mkdir()
    run(env, str(folder), extra_env={"TMPDIR": str(tmp)})
    assert list(tmp.iterdir()) == []


# ---------- terminal do desktop conforme XDG_CURRENT_DESKTOP (item 13) ----------

def test_kde_desktop_prefers_kreadconfig_over_gsettings(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "konsole")
    make_fake_terminal(fakebin, log, "kitty")
    make_fake_desktop_tool(fakebin, "gsettings", "'kitty'")
    make_fake_desktop_tool(fakebin, "kreadconfig6", "konsole")
    r = run(env, "--resolve-terminal", extra_env={"XDG_CURRENT_DESKTOP": "KDE"})
    assert r.stdout.strip() == "konsole"
    r = run(env, "--resolve-terminal", extra_env={"XDG_CURRENT_DESKTOP": "GNOME"})
    assert r.stdout.strip() == "kitty"


def test_kde_falls_back_to_gsettings_when_kreadconfig_is_empty(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "konsole")
    make_fake_terminal(fakebin, log, "kitty")
    make_fake_desktop_tool(fakebin, "gsettings", "'kitty'")
    make_fake_desktop_tool(fakebin, "kreadconfig6", "")
    r = run(env, "--resolve-terminal", extra_env={"XDG_CURRENT_DESKTOP": "KDE"})
    assert r.stdout.strip() == "kitty"


def test_gnome_falls_back_to_kreadconfig_when_gsettings_is_empty(launcher_env):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "konsole")
    make_fake_terminal(fakebin, log, "gnome-terminal")
    make_fake_desktop_tool(fakebin, "gsettings", "")
    make_fake_desktop_tool(fakebin, "kreadconfig5", "konsole")
    r = run(env, "--resolve-terminal", extra_env={"XDG_CURRENT_DESKTOP": "GNOME"})
    assert r.stdout.strip() == "konsole"


# ---------- --resolve-terminal --auto (item 11) ----------

def test_resolve_terminal_auto_ignores_configured_terminal(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "xterm")
    make_fake_terminal(fakebin, log, "kitty")
    cfg = tmp_path / "home" / ".config" / "claude-aqui"
    cfg.mkdir(parents=True)
    (cfg / "config").write_text("terminal=xterm\n")
    assert run(env, "--resolve-terminal").stdout.strip() == "xterm"
    r = run(env, "--resolve-terminal", "--auto")
    assert r.stdout.strip() == "kitty"
    assert r.stderr == ""


def test_resolve_terminal_auto_no_warning_for_uninstalled_choice(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, "kitty")
    cfg = tmp_path / "home" / ".config" / "claude-aqui"
    cfg.mkdir(parents=True)
    (cfg / "config").write_text("terminal=foot\n")
    r = run(env, "--resolve-terminal", "--auto")
    assert r.stdout.strip() == "kitty" and r.stderr == ""


# ---------- marcador de "terminal iniciou": sem seguir symlink (item 2, revisão de segurança) ----------

def _state_dir(tmp_path, mode=0o700, name="claude-aqui.AbC123"):
    d = tmp_path / "estado" / name
    d.mkdir(parents=True)
    d.chmod(mode)
    return d


def _run_inner_with_marker(launcher_env, tmp_path, marker):
    env, _, log = launcher_env
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    folder = tmp_path / "proj"
    folder.mkdir(exist_ok=True)
    r = run(env, "--run", str(folder), extra_env={"CLAUDE_AQUI_STARTED": str(marker)})
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>" in log.read_text()  # o claude sempre inicia
    return r


def test_marker_is_written_in_a_safe_state_dir(launcher_env, tmp_path):
    d = _state_dir(tmp_path)
    _run_inner_with_marker(launcher_env, tmp_path, d / "started")
    assert (d / "started").is_file()


def test_marker_symlink_to_victim_file_is_not_truncated(launcher_env, tmp_path):
    d = _state_dir(tmp_path)
    victim = tmp_path / "vitima.txt"
    victim.write_text("importante")
    (d / "started").symlink_to(victim)
    _run_inner_with_marker(launcher_env, tmp_path, d / "started")
    assert victim.read_text() == "importante"


def test_state_dir_replaced_by_symlink_does_not_touch_victim(launcher_env, tmp_path):
    victim_dir = tmp_path / "alvo"
    victim_dir.mkdir()
    victim_dir.chmod(0o700)
    victim = victim_dir / "started"
    victim.write_text("importante")
    link_parent = tmp_path / "estado"
    link_parent.mkdir()
    link = link_parent / "claude-aqui.AbC123"
    link.symlink_to(victim_dir)  # o diretório foi removido e recriado como symlink
    _run_inner_with_marker(launcher_env, tmp_path, link / "started")
    assert victim.read_text() == "importante"


def test_state_dir_with_wide_permissions_is_not_used(launcher_env, tmp_path):
    d = _state_dir(tmp_path, mode=0o777)
    _run_inner_with_marker(launcher_env, tmp_path, d / "started")
    assert not (d / "started").exists()


def test_marker_outside_a_claude_aqui_state_dir_is_ignored(launcher_env, tmp_path):
    d = _state_dir(tmp_path, name="qualquer")
    _run_inner_with_marker(launcher_env, tmp_path, d / "started")
    assert not (d / "started").exists()
    _run_inner_with_marker(launcher_env, tmp_path, tmp_path / "estado" / "claude-aqui.AbC123" / "outro")


def test_missing_state_dir_does_not_break_claude(launcher_env, tmp_path):
    _run_inner_with_marker(launcher_env, tmp_path, tmp_path / "sumiu" / "claude-aqui.x" / "started")
    assert not (tmp_path / "sumiu").exists()


def _record_state_env(fakebin, log):
    write_executable(fakebin / "kitty", f'printf "STATE<%s>\\n" "$CLAUDE_AQUI_STARTED" >> "{log}"\n')


def test_state_dir_uses_xdg_runtime_dir_when_available(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    _record_state_env(fakebin, log)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.chmod(0o700)
    tmpd = tmp_path / "tmpd"
    tmpd.mkdir()
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder), extra_env={"XDG_RUNTIME_DIR": str(runtime), "TMPDIR": str(tmpd)})
    assert r.returncode == 0, r.stderr
    assert f"STATE<{runtime}/claude-aqui." in log.read_text()
    assert list(runtime.iterdir()) == [] and list(tmpd.iterdir()) == []


def test_state_dir_falls_back_to_tmpdir_without_xdg_runtime_dir(launcher_env, tmp_path):
    env, fakebin, log = launcher_env
    _record_state_env(fakebin, log)
    tmpd = tmp_path / "tmpd"
    tmpd.mkdir()
    folder = tmp_path / "p"
    folder.mkdir()
    r = run(env, str(folder), extra_env={"TMPDIR": str(tmpd), "XDG_RUNTIME_DIR": str(tmp_path / "nao-existe")})
    assert r.returncode == 0, r.stderr
    assert f"STATE<{tmpd}/claude-aqui." in log.read_text()


# ---------- terminais acrescentados (item 3) ----------
# Flags confirmados com --help e execução em contêiner Fedora (veja final-fix-report.md).

NEW_TERMINALS = [
    # (id, argumentos esperados antes de --run, o caminho também vai no argv?)
    ("mate-terminal", ["--working-directory={d}", "-x"], True),
    ("foot", ["-D", "{d}"], True),
    ("terminator", ["--working-directory={d}", "-x"], False),
    ("lxterminal", ["--working-directory={d}", "-e"], False),
    ("ptyxis", ["--new-window", "--working-directory={d}", "--"], False),
]
STRING_E_TERMINALS = [
    # -e recebe UMA string que o terminal reparte: o caminho nunca entra nela
    ("tilix", ["--working-directory={d}", "-e"]),
    ("qterminal", ["-w", "{d}", "-e"]),
    ("kgx", ["--working-directory={d}", "-e"]),
]


@pytest.mark.parametrize("term,expected,path_in_argv", NEW_TERMINALS, ids=[t[0] for t in NEW_TERMINALS])
def test_new_terminal_flags(launcher_env, tmp_path, term, expected, path_in_argv):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, term)
    folder = tmp_path / "pasta com 'aspas' $x"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    args = [l[4:-1] for l in log.read_text().splitlines() if l.startswith("ARG<")]
    assert args[: len(expected)] == [e.format(d=folder) for e in expected]
    assert args[-2:] == ["--run", str(folder)] if path_in_argv else args[-1] == "--run"
    if not path_in_argv:
        assert str(folder) not in args[len(expected):]
    assert f"PWD<{folder}>" in log.read_text()


@pytest.mark.parametrize("term,expected", STRING_E_TERMINALS, ids=[t[0] for t in STRING_E_TERMINALS])
def test_string_e_terminal_gets_single_quoted_command_without_folder(launcher_env, tmp_path, term, expected):
    env, fakebin, log = launcher_env
    make_fake_terminal(fakebin, log, term)
    folder = tmp_path / "pasta"
    folder.mkdir()
    r = run(env, str(folder))
    assert r.returncode == 0, r.stderr
    args = [l[4:-1] for l in log.read_text().splitlines() if l.startswith("ARG<")]
    assert args[: len(expected)] == [e.format(d=folder) for e in expected]
    command = args[len(expected)]
    assert command == f"'{LAUNCHER}' --run" and len(args) == len(expected) + 1
    assert str(folder) not in command


@pytest.mark.parametrize("term", [t[0] for t in STRING_E_TERMINALS])
@pytest.mark.parametrize("name", HOSTILE, ids=lambda n: repr(n))
def test_string_e_terminals_run_inner_with_hostile_folder_and_spaced_launcher(launcher_env, tmp_path, term, name):
    """O terminal reparte a string do -e como o shell: lançador com espaço e apóstrofo no caminho."""
    env, fakebin, log = launcher_env
    safe_bin = tmp_path / "bin com 'aspas'"
    safe_bin.mkdir()
    launcher = safe_bin / "claude-aqui-launch"
    launcher.write_bytes(LAUNCHER.read_bytes())
    launcher.chmod(0o755)
    # terminal falso: roda o valor de -e via sh -c, como um terminal que junta/reparte a string
    write_executable(fakebin / term, 'while [ "$1" != "-e" ]; do shift; done; sh -c "$2"\n')
    make_fake_claude(tmp_path / "home" / ".local" / "bin" / "claude", log)
    base = tmp_path / "work"
    base.mkdir()
    folder = base / name
    folder.mkdir()
    r = subprocess.run(["/bin/sh", str(launcher), str(folder)], env=env, cwd=base,
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    assert f"CLAUDE<{folder}>\n" in log.read_text()
    assert not (base / "X").exists() and not (folder / "X").exists()


def test_new_terminals_are_listed_when_installed(launcher_env):
    env, fakebin, log = launcher_env
    for t, *_ in NEW_TERMINALS + STRING_E_TERMINALS:
        make_fake_terminal(fakebin, log, t)
    assert set(run(env, "--list-terminals").stdout.split()) == {
        t for t, *_ in NEW_TERMINALS + STRING_E_TERMINALS}
