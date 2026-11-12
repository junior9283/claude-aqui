# Claude Aqui — Plano de Implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** app GTK4 que instala/remove "Abrir Claude Code aqui" nos menus de botão direito de Nautilus, Caja, Dolphin, Nemo, Thunar e PCManFM-Qt, distribuído em `.deb`, `.rpm` e `PKGBUILD`.

**Arquitetura:** (1) lançador `claude-aqui-launch` em `sh` — única fonte de verdade para caminho, terminais e localização do `claude`; (2) pacote Python `claude_aqui` com um `FileManager` por gerenciador (gera/remove arquivos de menu do usuário), uma camada `service` testável sem GUI, CLI headless e GUI fina; (3) empacotamento via `make install DESTDIR=` reaproveitado pelos três formatos. Os itens de menu chamam um *stub* por usuário (`~/.local/share/claude-aqui/menu-stub`) que verifica se o lançador ainda existe antes de executá-lo.

**Tech Stack:** sh (POSIX), Python 3 + PyGObject (GTK4 + libadwaita), pytest, make, dpkg-deb, rpmbuild, makepkg, podman/docker para testes de pacote.

**Spec:** `docs/superpowers/specs/2026-11-12-claude-aqui-design.md`

## Restrições globais

- Alvo: distros atuais com GTK4/libadwaita (Ubuntu 22.04+, Debian 12+, Mint 22+, Fedora/Nobara atuais, openSUSE Leap 15.5+, Arch). Sem suporte a Ubuntu 20.04, Debian 11, Mint 21.
- Nome do item de menu: **"Abrir Claude Code aqui"**. Interface e mensagens em pt-BR.
- Menu instalado só no usuário (`$XDG_DATA_HOME`/`~/.local/share`, `$XDG_CONFIG_HOME`/`~/.config`), nunca com root.
- O caminho da pasta nunca é interpolado em string de shell; passa sempre como argumento.
- Ao sair do `claude` o terminal fecha; em erro (claude não encontrado, pasta inválida) mostra a mensagem e espera uma tecla.
- Nunca sobrescrever arquivo de menu sem a marca `claude-aqui-managed`; avisar e pular o gerenciador (`ConflictError`).
- Ordem de resolução do terminal: escolha do usuário → `xdg-terminal-exec` → `x-terminal-emulator` → configuração do desktop (gsettings GNOME / `kreadconfig` KDE) → lista de terminais conhecidos. Terminal escolhido e desinstalado: cair no automático e avisar.
- Locais extras para achar o `claude`: `~/.local/bin`, `~/.claude/local`, `~/.npm-global/bin`, nvm, `/usr/local/bin`, `/usr/bin`.
- Sem `sudo`, sem segredos, sem `git push`. Commits em pt-BR, terminando com a linha `Co-Authored-By` exigida pelo ambiente.
- Processo do usuário: após codificar cada tarefa, rodar a skill `simplify` sobre o código criado e só então os testes; antes do commit, lint + testes da tarefa.

## Desvio conhecido da spec (confirmar com o usuário na entrega)

Nautilus e Caja só permitem **scripts**, que aparecem no submenu "Scripts" e **também em arquivos** (não dá para restringir a pastas sem a extensão `python3-nautilus`/`caja-python`, dependência extra). Neste plano o script, ao receber um arquivo, mostra "Selecione uma pasta." e não faz nada. Nos demais gerenciadores o item aparece só em pastas e no fundo de pasta aberta.

## Foco da revisão (casos que a spec implica e nenhum teste de rotina cobriria)

1. Caminho hostil (espaços, aspas, `$`, crase, `;`, quebra de linha, `\n` literal, `%` literal) chega intacto ao terminal. → Task 1.
2. `HOME` com espaço: Exec/arquivos de menu continuam válidos. → Tasks 3 e 4.
3. Arquivo do usuário já existente no mesmo caminho nunca é sobrescrito nem apagado. → Task 2.
4. `uca.xml` do Thunar ausente, malformado ou com ações do usuário. → Task 5.
5. Terminal configurado foi desinstalado, ou nenhum terminal existe: fallback com aviso / erro visível, nunca silêncio. → Tasks 1 e 6.
6. `claude` só em `~/.npm-global/bin` (fora do PATH do gerenciador de arquivos). → Task 1.

## Estrutura de arquivos

```
bin/claude-aqui-launch          lançador sh
bin/claude-aqui                 ponto de entrada Python (GUI e CLI)
claude_aqui/__init__.py
claude_aqui/base.py             MARKER, Status, ConflictError, Context, FileManager
claude_aqui/launcher.py         cliente Python do lançador (--list-terminals etc.)
claude_aqui/config.py           lê/grava ~/.config/claude-aqui/config
claude_aqui/managers/{nautilus,caja,dolphin,nemo,thunar,pcmanfm}.py
claude_aqui/service.py          snapshot(), set_manager(), set_terminal(), remove_all()
claude_aqui/cli.py              --status/--enable/--disable/--remove-all/GUI
claude_aqui/gui.py              janela Adw
data/claude-aqui.desktop, data/claude-aqui.svg
Makefile                        install/dist/deb/rpm
packaging/{deb/control.in, rpm/claude-aqui.spec, arch/PKGBUILD}
scripts/test-packages.sh        teste de instalação em contêineres
tests/{conftest.py, launcher/, managers/, test_*.py}
docs/testes/README.md           guia da suíte e registro de bugs
README.md
```

---

### Task 1: Lançador `claude-aqui-launch` + esqueleto do repositório

**Arquivos:**
- Criar: `bin/claude-aqui-launch`, `.gitignore`, `pytest.ini`, `tests/conftest.py`, `tests/launcher/test_launcher.py`
- Rodar `git init` na raiz (a pasta ainda não é repositório).

**Interfaces — Produz** (CLI do lançador, usado por todas as outras tarefas):
- `claude-aqui-launch [CAMINHO]` — modo externo: resolve a pasta, resolve o terminal, abre o terminal rodando `claude-aqui-launch --run PASTA`.
- `claude-aqui-launch --run PASTA` — modo interno (dentro do terminal): `cd`, `exec claude`; em erro, imprime a mensagem e espera uma tecla.
- `--find-claude` → imprime o caminho do `claude` (exit 0) ou nada (exit 1).
- `--list-terminals` → ids dos terminais conhecidos instalados, um por linha.
- `--resolve-terminal` → imprime o id efetivo (exit 1 se nenhum); avisos em stderr.
- Sem argumento, lê `NAUTILUS_SCRIPT_SELECTED_FILE_PATHS`/`CAJA_SCRIPT_SELECTED_FILE_PATHS` (primeira linha) e, se vazio, `*_SCRIPT_CURRENT_URI`. Aceita `file://` com percent-encoding.
- Config lida de `${XDG_CONFIG_HOME:-$HOME/.config}/claude-aqui/config`, linha `terminal=ID` (lida com `sed`, nunca com `source`).
- Erros vão por `notify-send`, depois `zenity`/`kdialog`, depois stderr.

Ids de terminais obrigatórios: `gnome-terminal`, `konsole`, `kitty`, `alacritty`, `xfce4-terminal`; incluir também `foot`, `wezterm`, `lxterminal`, `mate-terminal`, `xterm` e `ptyxis`/`kgx` quando os flags forem confirmados com `--help` do binário. Cada terminal usa seus flags de diretório e de execução de comando como lista de argumentos; o processo externo também faz `cd PASTA`.

- [ ] **Passo 1: `git init`, `.gitignore` (`__pycache__/`, `*.pyc`, `dist/`, `build/`), `pytest.ini` (`testpaths = tests`).**
- [ ] **Passo 2: `tests/conftest.py` com fixture `launcher_env(tmp_path)`** que devolve `(env, fakebin, log)`: `PATH` = `fakebin` + `/usr/bin:/bin`, `HOME` e `XDG_CONFIG_HOME` em `tmp_path`; helper `make_fake_terminal(name)` cria em `fakebin` um executável que grava `pwd` e cada argumento (um por linha) em `log`.
- [ ] **Passo 3: escrever os testes (devem falhar)** em `tests/launcher/test_launcher.py`:
  - `test_hostile_path_arrives_intact` (parametrizado: `a b`, `a'b"c`, `$(touch X)`, `` `touch X` ``, `a;b`, `a\nb` com quebra real, `a\\nb` com barra+n literal, `100%25`, `%41` literal): cria a pasta, roda com `xterm` falso; assert que o log contém a pasta exata como um único argumento e que o arquivo `X` não existe.
  - `test_file_uri_is_decoded`: `file:///tmp/x/a%20b` → pasta `a b`.
  - `test_nautilus_env_first_selected_path_is_used` e `test_current_uri_used_when_no_selection`.
  - `test_not_a_directory_shows_error_and_exits_1`: arquivo comum → exit 1, mensagem "Selecione uma pasta." no stderr (sem `notify-send` falso no PATH).
  - `test_configured_terminal_is_used` e `test_configured_terminal_uninstalled_falls_back_with_warning` (stderr contém aviso; usa o terminal automático).
  - `test_no_terminal_installed_reports_error` (exit 1, mensagem visível).
  - `test_resolve_order`: com `xdg-terminal-exec` e `kitty` falsos, `--resolve-terminal` escolhe `xdg-terminal-exec`; sem ele, `x-terminal-emulator`; sem ambos, cai na lista.
  - `test_list_terminals_only_lists_installed`.
  - `test_find_claude_in_npm_global_outside_path`: `claude` falso em `$HOME/.npm-global/bin`, fora do PATH → `--find-claude` imprime esse caminho.
  - `test_run_mode_execs_claude_in_folder` (claude falso grava `pwd`) e `test_run_mode_without_claude_prints_message_and_waits_for_key` (stdin `\n` → termina, mensagem em pt-BR no stdout).
- [ ] **Passo 4: rodar `pytest tests/launcher -v` e confirmar que falha** ("No such file").
- [ ] **Passo 5: implementar `bin/claude-aqui-launch` (sh POSIX, `chmod +x`).** Decodificação de percent-encoding com `awk` ou `printf` sem interpretar barras invertidas do resto do texto; o caminho decodificado só é manipulado entre aspas e passado como `"$@"`/`set --`.
- [ ] **Passo 6: rodar a skill `simplify` sobre o arquivo; depois `shellcheck bin/claude-aqui-launch` (se instalado) e `pytest tests/launcher -v` → todos passam.**
- [ ] **Passo 7: commit** `feat: lançador claude-aqui-launch com resolução de terminal e caminhos seguros`.

---

### Task 2: Núcleo Python (`base`, `config`, cliente do lançador, stub)

**Arquivos:**
- Criar: `claude_aqui/__init__.py`, `claude_aqui/base.py`, `claude_aqui/config.py`, `claude_aqui/launcher.py`, `tests/test_base.py`, `tests/test_config.py`, `tests/test_launcher_client.py`

**Interfaces — Produz:**
```python
MARKER = "claude-aqui-managed"
class Status(enum.Enum): NOT_INSTALLED; DISABLED; ENABLED; CONFLICT
class ConflictError(Exception): path: Path
@dataclass
class Context:
    home: Path
    launcher: str = os.environ.get("CLAUDE_AQUI_LAUNCHER", "/usr/bin/claude-aqui-launch")
    data_dir -> Path    # $XDG_DATA_HOME ou home/.local/share
    config_dir -> Path  # $XDG_CONFIG_HOME ou home/.config
    stub_path -> Path   # data_dir/claude-aqui/menu-stub
    def ensure_stub(self) -> Path   # cria/atualiza o stub (marca, 0755); chamado por enable()
class FileManager(ABC):
    id: str; name: str; binaries: tuple[str, ...]
    def __init__(self, ctx: Context)
    def is_installed(self) -> bool            # any(shutil.which(b))
    @abstractmethod def entries(self) -> list[Path]   # arquivos que o app cria
    def status(self) -> Status
    def enable(self) -> None                  # ConflictError se algum entry existe sem MARKER
    @abstractmethod def render(self, entry: Path) -> tuple[str, int]  # (conteúdo, modo)
    def disable(self) -> None                 # apaga só entries com MARKER
def load_terminal(ctx) -> str | None   # config.py
def save_terminal(ctx, terminal: str | None) -> None   # None remove a escolha
# launcher.py
def list_terminals() -> list[str]; def resolve_terminal() -> str | None; def find_claude() -> str | None
```
O stub (`sh`): se `[ -x LAUNCHER ]` falta, `notify-send "Claude Aqui" "O Claude Aqui foi desinstalado; remova este item do menu."` e `exit 1`; senão `exec LAUNCHER "$@"`. Caminho do lançador entre aspas, com escape correto.

- [ ] **Passo 1: testes (falham):**
  - `test_enable_blocks_foreign_file` : entry já existe sem MARKER → `ConflictError`, arquivo intacto, nenhum outro entry criado; `status()` = `CONFLICT`.
  - `test_disable_never_deletes_foreign_file`; `test_disable_removes_only_marked_entries`; `test_enable_is_idempotent`.
  - `test_status_transitions` (`DISABLED` → `ENABLED` → `DISABLED`; `NOT_INSTALLED` quando nenhum binário no PATH).
  - `test_stub_reports_missing_launcher` (executa o stub com `launcher` inexistente e `notify-send` falso → exit 1 e mensagem) e `test_stub_execs_launcher_with_args_intact` (home com espaço, argumento hostil).
  - `test_config_roundtrip` e `test_save_none_removes_choice`; `test_config_ignores_malformed_lines`.
  - `test_launcher_client_parses_outputs` com lançador falso via `CLAUDE_AQUI_LAUNCHER`.
  Usar um `FileManager` fake de teste definido em `tests/test_base.py`.
- [ ] **Passo 2:** `pytest tests/test_base.py tests/test_config.py tests/test_launcher_client.py -v` → falha.
- [ ] **Passo 3: implementar** os três módulos conforme as assinaturas. `enable()` primeiro checa todos os entries (sem escrever nada se houver conflito), depois `ctx.ensure_stub()` e grava cada entry com `render()`. Escrita atômica (arquivo temporário + `os.replace`).
- [ ] **Passo 4:** `simplify`, depois os testes → passam.
- [ ] **Passo 5: commit** `feat: núcleo Python com FileManager, config e stub do menu`.

---

### Task 3: Nautilus e Caja (scripts)

Independente das Tasks 4 e 5 (arquivos diferentes): pode rodar em paralelo em worktree.

**Arquivos:** Criar `claude_aqui/managers/__init__.py` (vazio; a Task 6 o preenche com o registro), `nautilus.py`, `caja.py`, `tests/managers/test_script_managers.py`.

**Interfaces — Consome:** `FileManager`, `Context` (Task 2). **Produz:** `NautilusManager` (`id="nautilus"`, `name="Arquivos (Nautilus)"`, binário `nautilus`, entry `data_dir/nautilus/scripts/Abrir Claude Code aqui`) e `CajaManager` (`id="caja"`, `name="Caja"`, binário `caja`, entry `config_dir/caja/scripts/Abrir Claude Code aqui`).

Conteúdo do script: `#!/bin/sh`, comentário com `MARKER`, `exec "<stub>"` (sem argumentos: o lançador lê as variáveis de ambiente do gerenciador). Modo `0755`.

- [ ] **Passo 1: testes (falham):** `test_enable_creates_executable_script` (modo, MARKER, referência ao stub), `test_script_works_with_home_containing_space` (home `tmp/"meu home"`; executar o script com `NAUTILUS_SCRIPT_SELECTED_FILE_PATHS` apontando para uma pasta e lançador falso → lançador falso recebe a pasta), `test_disable_removes_script`, `test_foreign_script_conflict`.
- [ ] **Passo 2:** rodar → falha. **Passo 3:** implementar os dois managers. **Passo 4:** `simplify` + testes → passam.
- [ ] **Passo 5: commit** `feat: itens de menu do Nautilus e Caja`.

---

### Task 4: Dolphin, Nemo e PCManFM-Qt (arquivos `.desktop`/`.nemo_action`)

Independente das Tasks 3 e 5.

**Arquivos:** Criar `claude_aqui/managers/{dolphin,nemo,pcmanfm}.py`, `tests/managers/test_desktop_managers.py`.

**Interfaces — Produz:**
- `DolphinManager` (`id="dolphin"`, binário `dolphin`): `data_dir/kio/servicemenus/claude-aqui.desktop`, `Type=Service`, `MimeType=inode/directory;`, `Actions=OpenClaude;`, `X-KDE-Priority=TopLevel`, seção `[Desktop Action OpenClaude]` com `Name=Abrir Claude Code aqui`, `Exec` = stub + `%f`; `X-ClaudeAqui=claude-aqui-managed`; modo `0755`.
- `NemoManager` (`id="nemo"`, binário `nemo`): dois entries em `data_dir/nemo/actions/`: `claude-aqui.nemo_action` (`Selection=s`, `Extensions=dir`, `Exec` stub + `%F`) e `claude-aqui-bg.nemo_action` (`Selection=none`, `Exec` stub + `%P`, fundo da pasta); marca em comentário `# claude-aqui-managed`.
- `PcmanfmManager` (`id="pcmanfm-qt"`, binário `pcmanfm-qt`): `data_dir/file-manager/actions/claude-aqui.desktop` com `Type=Action`, `Profiles=profile-1;`, `[X-Action-Profile profile-1]` com `MimeTypes=inode/directory;` e `Exec` stub + `%f`; `X-ClaudeAqui=claude-aqui-managed`.
- Em todos, o caminho do stub no `Exec` fica entre aspas duplas com escape conforme a Desktop Entry Spec (home com espaço).

- [ ] **Passo 1: testes (falham):** por manager, `test_enable_writes_expected_keys` (chaves acima), `test_exec_quotes_stub_path_with_space` (parse do `Exec` com `shlex.split` devolve o stub como um único argumento), `test_disable_removes_only_ours`, `test_foreign_file_conflict`; no Nemo, `test_background_action_uses_selection_none`. Se `desktop-file-validate` existir, validar também os `.desktop` gerados (`skipif` ausente).
- [ ] **Passo 2:** falha. **Passo 3:** implementar. **Passo 4:** confirmar as chaves do Nemo/Dolphin/libfm na documentação oficial (ferramenta `ctx7`) antes de fixar. **Passo 5:** `simplify` + testes → passam.
- [ ] **Passo 6: commit** `feat: itens de menu do Dolphin, Nemo e PCManFM-Qt`.

---

### Task 5: Thunar (`uca.xml`)

Independente das Tasks 3 e 4.

**Arquivos:** Criar `claude_aqui/managers/thunar.py`, `tests/managers/test_thunar.py`.

**Interfaces — Produz:** `ThunarManager` (`id="thunar"`, binário `thunar`) que edita `config_dir/Thunar/uca.xml`. Nossa ação: `<unique-id>claude-aqui-1</unique-id>`, `<name>Abrir Claude Code aqui</name>`, `<command>"STUB" %f</command>`, `<patterns>*</patterns>`, `<directories/>`. Reimplementa `entries()`/`status()`/`enable()`/`disable()` (não usa arquivos próprios): a "marca" é o prefixo `claude-aqui-` no `unique-id`.

- [ ] **Passo 1: testes (falham):** `test_creates_uca_when_missing` (estrutura válida `<actions>`), `test_preserves_user_actions_and_order`, `test_enable_twice_does_not_duplicate`, `test_disable_removes_only_ours_and_keeps_user_actions`, `test_malformed_xml_raises_conflict_and_file_untouched`, `test_backup_created_before_first_edit` (`uca.xml.claude-aqui.bak`, só se o arquivo já existia e ainda não há backup), `test_command_quotes_stub_with_space`.
- [ ] **Passo 2:** falha. **Passo 3:** implementar com `xml.etree.ElementTree`, escrita atômica. Fica registrado como aviso na GUI (Task 7): "Feche o Thunar antes de ativar; ele pode regravar o arquivo".
- [ ] **Passo 4:** confirmar com a documentação do Thunar (`ctx7`/man) o comportamento de `%f` no fundo da pasta; se não funcionar no fundo, documentar a limitação em `README.md`. **Passo 5:** `simplify` + testes → passam.
- [ ] **Passo 6: commit** `feat: item de menu do Thunar via uca.xml`.

---

### Task 6: Registro, `service` e CLI headless

**Arquivos:** Modificar `claude_aqui/managers/__init__.py`; criar `claude_aqui/service.py`, `claude_aqui/cli.py`, `bin/claude-aqui`, `tests/test_service.py`, `tests/test_cli.py`.

**Interfaces — Consome:** todos os managers, `config`, `launcher`. **Produz:**
```python
def all_managers(ctx: Context) -> list[FileManager]   # ordem: nautilus, dolphin, nemo, caja, thunar, pcmanfm-qt
@dataclass class ManagerRow: id: str; name: str; status: Status; message: str | None
@dataclass class AppSnapshot:
    managers: list[ManagerRow]; terminals: list[str]
    configured_terminal: str | None; effective_terminal: str | None
    terminal_fallback: bool      # escolhido não instalado -> usando automático
    claude_path: str | None
def snapshot(ctx) -> AppSnapshot
def set_manager(ctx, manager_id: str, enabled: bool) -> None   # propaga ConflictError
def set_terminal(ctx, terminal: str | None) -> None
def remove_all(ctx) -> None    # disable() em todos + remove stub + remove config
```
CLI (`claude-aqui`): sem argumentos abre a GUI; `--status`, `--enable ID|all`, `--disable ID|all`, `--remove-all`; `main(argv=None) -> int`. `--enable all` ignora gerenciadores `NOT_INSTALLED` e retorna 1 se houver `CONFLICT`, mas continua nos demais.

- [ ] **Passo 1: testes (falham):** `test_snapshot_marks_conflict_with_message`, `test_snapshot_flags_terminal_fallback_when_configured_one_missing`, `test_snapshot_claude_path_none_when_missing`, `test_set_manager_roundtrip`, `test_set_manager_conflict_leaves_state_unchanged`, `test_remove_all_deletes_every_entry_stub_and_config` (e não toca arquivos alheios), `test_cli_enable_all_skips_not_installed`, `test_cli_exit_code_on_conflict`, `test_cli_status_output_lists_each_manager`. Binários dos gerenciadores simulados com executáveis falsos em `PATH`.
- [ ] **Passo 2:** falha. **Passo 3:** implementar; `bin/claude-aqui` é um script Python curto que adiciona o diretório da lib ao `sys.path` (substituído no `make install`) e chama `cli.main()`.
- [ ] **Passo 4:** `simplify` + testes → passam. **Passo 5: commit** `feat: serviço, registro de gerenciadores e CLI headless`.

---

### Task 7: Interface gráfica (GTK4 + libadwaita)

**Arquivos:** Criar `claude_aqui/gui.py`, `tests/test_gui_smoke.py`; modificar `cli.py` para chamar `gui.run()`.

**Interfaces — Consome:** `service.*`. **Produz:** `run() -> int` (Adw.Application `br.app.ClaudeAqui`).

Janela: `Adw.PreferencesPage` com
- `Adw.Banner` "Claude Code não encontrado. Instale-o e reabra este app." quando `claude_path is None`;
- grupo **Gerenciadores de arquivos**: uma `Adw.SwitchRow` por gerenciador (subtítulo: "Ativado" / "Desativado" / "Não instalado" — linha desabilitada / mensagem do conflito); no Thunar, subtítulo adicional com o aviso para fechar o Thunar;
- grupo **Terminal**: `Adw.ComboRow` "Automático (detectado: X)" + terminais instalados; se `terminal_fallback`, subtítulo avisa que o terminal escolhido foi desinstalado;
- botão destrutivo **Remover tudo** com `Adw.AlertDialog` de confirmação.
- Erro em `set_manager` (`ConflictError`): `Adw.Toast` com a mensagem e o switch volta ao estado real.

- [ ] **Passo 1: teste (falha) `test_gui_builds_window_from_snapshot`:** com `Gtk.init_check()` falso → `skip`; senão constrói a janela com um `AppSnapshot` fixo e confere o número de linhas e que a linha "Não instalado" está insensível. Separar a construção da janela (`build_window(app, snapshot_fn)`) da execução para permitir o teste.
- [ ] **Passo 2:** falha. **Passo 3:** implementar. **Passo 4:** `simplify`; rodar o app de verdade (`python3 bin/claude-aqui`), alternar um gerenciador, trocar o terminal, "Remover tudo", e conferir os arquivos em disco. Registrar o resultado.
- [ ] **Passo 5: commit** `feat: interface gráfica GTK4/libadwaita`.

---

### Task 8: Instalação (`make install`), ícone, `.desktop` e README

**Arquivos:** Criar `Makefile`, `data/claude-aqui.desktop`, `data/claude-aqui.svg`, `README.md`.

**Interfaces — Produz:** `make install PREFIX=/usr DESTDIR=...` instala `bin/claude-aqui`, `bin/claude-aqui-launch` em `$(PREFIX)/bin`; `claude_aqui/` em `$(PREFIX)/lib/claude-aqui/`; `.desktop` em `share/applications`; ícone em `share/icons/hicolor/scalable/apps`. O `bin/claude-aqui` instalado tem o `sys.path` e o caminho do lançador (`$(PREFIX)/bin/claude-aqui-launch`, exportado ao `Context` por `CLAUDE_AQUI_LAUNCHER` default) substituídos via `sed`. `make dist VERSION=x.y.z` gera `dist/claude-aqui-x.y.z.tar.gz`. `make uninstall` remove tudo o que foi instalado.

- [ ] **Passo 1: teste (falha) `tests/test_install.py::test_make_install_layout`:** `make install DESTDIR=tmp PREFIX=/usr` e confere a árvore; `test_installed_launcher_path_is_patched`; `test_make_uninstall_leaves_empty_tree`.
- [ ] **Passo 2:** falha. **Passo 3:** implementar o `Makefile`, `.desktop` (`Name=Claude Aqui`, `Categories=Utility;`, `Exec=claude-aqui`) e um ícone SVG simples; `README.md` em pt-BR (o que faz, gerenciadores, desvio Nautilus/Caja, como instalar pelos pacotes, remover tudo).
- [ ] **Passo 4:** `desktop-file-validate data/claude-aqui.desktop` (se instalado) e testes → passam. **Passo 5: commit** `feat: instalação via make, ícone e README`.

---

### Task 9: Pacotes `.deb`, `.rpm` e `PKGBUILD`

Os três pacotes são independentes entre si (depois da Task 8); podem ser feitos em paralelo.

**Arquivos:** Criar `packaging/deb/control.in`, `packaging/rpm/claude-aqui.spec`, `packaging/arch/PKGBUILD`; modificar `Makefile` (alvos `deb`, `rpm`, `arch-src`).

**Dependências por formato:**
- deb: `Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1`; `Recommends: libnotify-bin`.
- rpm: `Requires: python3, python3-gobject, gtk4, libadwaita`; `Recommends: libnotify`.
- Arch: `depends=(python python-gobject gtk4 libadwaita)`, `optdepends=('libnotify: avisos do menu')`.
- Nos três, sem scripts de pós-instalação que toquem em pastas de usuários.

- [ ] **Passo 1: `make deb`** — `dpkg-deb --build` a partir de `make install DESTDIR=build/deb`, com `control` gerado de `control.in` (versão e arquitetura `all`). Verificar: `dpkg-deb -I` e `dpkg-deb -c` listam os arquivos esperados.
- [ ] **Passo 2: `make rpm`** — `rpmbuild -bb` sobre o tarball de `make dist`; verificar com `rpm -qlp` e `rpm -qp --requires`.
- [ ] **Passo 3: `PKGBUILD`** com `source=("claude-aqui-$pkgver.tar.gz")` local e `package()` chamando `make install DESTDIR="$pkgdir" PREFIX=/usr`; verificar com `namcap` quando disponível (dentro do contêiner Arch, Task 10).
- [ ] **Passo 4:** `desktop-file-validate`/`lintian`/`rpmlint` quando disponíveis; registrar avisos aceitos. **Passo 5: commit** `feat: pacotes deb, rpm e PKGBUILD`.

---

### Task 10: Testes de pacote em contêineres, guia de testes e passada de segurança

**Arquivos:** Criar `scripts/test-packages.sh`, `docs/testes/README.md`.

`scripts/test-packages.sh <deb|rpm|arch>` usa `podman` (ou `docker`) com imagens: deb → `debian:12` e `ubuntu:22.04`; rpm → `fedora:latest`; arch → `archlinux:latest`. Em cada uma: instala as dependências de build, gera o pacote, instala, cria usuário comum, coloca executáveis falsos dos seis gerenciadores no `PATH`, e como esse usuário roda `claude-aqui --enable all` → confere os arquivos esperados → `--disable all`/`--remove-all` → confere que nada sobrou em `~/.local`/`~/.config`. Também roda `claude-aqui-launch --list-terminals` e `--find-claude`. Sai com código ≠ 0 em qualquer falha.

- [ ] **Passo 1:** escrever o script; rodar para cada formato e capturar a saída (`PASS`/`FAIL` por imagem).
- [ ] **Passo 2: passada de segurança com a skill `testes-suite-padrao`**, escopo reduzido ao que se aplica (sem web/Supabase): injeção de comando pelo caminho, sobrescrita de arquivos alheios, permissões dos arquivos gerados, nenhum segredo no repositório. Cada achado vira teste que reproduz + registro em `docs/testes/README.md` (sintoma → causa → correção → teste → lição).
- [ ] **Passo 3:** `docs/testes/README.md` com: como rodar `pytest`, `scripts/test-packages.sh`, armadilhas conhecidas (ex.: Thunar regravando `uca.xml`, flags de terminais), registro de bugs.
- [ ] **Passo 4:** suíte completa: `pytest -v` e os três formatos de pacote → todos passam.
- [ ] **Passo 5: commit** `test: testes de pacote em contêineres e guia de testes`.

---

## Autorrevisão

- **Cobertura da spec:** gerenciadores (Tasks 3–5), terminal automático + escolha (Tasks 1, 6, 7), três formatos de pacote (Task 9), alvo GTK4 (restrições + dependências), lançador sh e caminho seguro (Task 1), conflitos/Thunar/backup (Tasks 2, 5), "Remover tudo" e stub que avisa se o lançador sumiu (Tasks 2, 6, 7), aviso de `claude` ausente (Tasks 1, 7), terminal fecha ao sair e espera tecla em erro (Task 1). Desvio de Nautilus/Caja registrado acima.
- **Tipos consistentes:** `Context`, `FileManager`, `Status`, `ConflictError`, `AppSnapshot`/`ManagerRow` usados com os mesmos nomes nas Tasks 2–7.
- **Ordem e paralelismo:** 1 → 2 → {3, 4, 5} em paralelo → 6 → 7 → 8 → {9 deb/rpm/arch} em paralelo → 10.
