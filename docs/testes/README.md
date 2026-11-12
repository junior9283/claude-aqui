# Guia de testes do Claude Aqui

## Como rodar

Testes unitários e de integração (Python, com o venv do projeto; GTK é pulado se faltar):

    .venv/bin/python -m pytest -q          # rápido
    .venv/bin/python -m pytest -v          # completo, com nomes
    .venv/bin/python -m pytest -q tests/managers/test_thunar.py   # só o que mudou

Os testes usam `HOME`/`XDG_*` em `tmp_path`: nunca tocam em `~/.config` ou `~/.local` reais.

Pacotes em contêineres (precisa de `podman`, ou `docker` como alternativa):

    scripts/test-packages.sh deb     # debian:12 e ubuntu:22.04
    scripts/test-packages.sh rpm     # fedora:latest e opensuse/tumbleweed (zypper)
    scripts/test-packages.sh arch    # archlinux:latest

Cada imagem baixa dependências, gera o pacote (`make deb|rpm|arch-src` + `makepkg`), instala,
cria um usuário comum com executáveis falsos dos seis gerenciadores e roda
`--enable all` → confere os arquivos → `--disable all` → `--enable all` → `--remove-all` →
confere que não sobrou nenhum arquivo em `~/.local`/`~/.config`. Também chama
`--list-terminals` e `--find-claude`. Saída `PASS`/`FAIL` por imagem; código ≠ 0 se qualquer
uma falhar. O repositório é montado só para leitura e copiado para `/tmp/work` no contêiner.
Leva alguns minutos por imagem (download de dependências).

## Cadência

| Momento | O que rodar |
|---|---|
| Por tarefa, enquanto codifica | só os testes do que mudou |
| Antes de cada commit | `pytest -q` completo (rápido, < 1 min) |
| Fim de etapa / mudança de risco (empacotamento, segurança, remoção de arquivos) | `pytest -v` + os três `test-packages.sh` |

## Armadilhas conhecidas

- **Thunar regrava o `uca.xml`** ao fechar/editar ações; nosso código só mexe na ação
  `claude-aqui-*`, preserva as demais e guarda um `.claude-aqui.bak` antes da primeira edição
  de um arquivo existente. Se o arquivo só continha a nossa ação (e não há backup), ele é apagado
  ao desativar.
- **Flags dos terminais:** os testes usam terminais falsos que gravam o argv. Os acrescentados na
  onda final (mate-terminal, terminator, lxterminal, tilix, qterminal) foram **executados de
  verdade** num contêiner Fedora com Xvfb e um script gravador, com pasta hostil
  (`dir with 'q' $x`): o cwd e o argv chegaram intactos. foot só foi confirmado por `--help`
  (precisa de Wayland). xterm/x-terminal-emulator/xdg-terminal-exec, tilix e qterminal recebem a
  pasta pelo cwd herdado e por um flag de diretório, nunca no argv/na string do `-e`.
- **Terminal falso do lançador:** o terminal agora roda sem `exec`; o lançador espera e avisa se ele
  sair com status != 0 sem o modo interno ter criado o marcador. Em testes que usam terminais
  falsos que saem com erro, o PATH do teste precisa de `mktemp`, `rm`, `rmdir` e `ls`
  (veja `SYSTEM_TOOLS` em `tests/conftest.py`).
- **GTK: não troque o modelo de um `Adw.ComboRow` dentro de `notify::selected`** (o `refresh()`
  chamado pelo handler travava em laço); a GUI só recria o modelo se os rótulos mudarem.
- **`XDG_CONFIG_DIRS` nos testes:** um `autouse` em `tests/conftest.py` o aponta para uma pasta
  inexistente, para que o `/etc/xdg/Thunar/uca.xml` da máquina não vire semente nos testes.
- **Pasta `dist/`/`build/` ignoradas pelo git** escondem sujeira no `git status`: confira
  `ls dist build` depois da suíte (os testes de pacote usam `tmp_path`).
- **`Gtk.MessageDialog` está deprecado desde o GTK 4.10** e a GUI o usa de propósito (é a única
  opção de diálogo disponível no GTK 4.6 do Ubuntu 22.04); gera `DeprecationWarning` em GTK novo.
  Trocar por `Gtk.AlertDialog` só quando o piso subir.
- **libadwaita 1.1 é o piso** (Ubuntu 22.04): `test_gui_nao_usa_apis_posteriores_ao_libadwaita_1_1`
  varre `gui.py` atrás de uma lista negra (`Adw.Banner`, `Adw.SwitchRow`, `Adw.AlertDialog`,
  `Adw.MessageDialog`, `Adw.ToolbarView`, `Gtk.AlertDialog`...). Os testes de GUI são pulados sem display.
- **Caminhos com espaço** (o projeto vive em "CLAUDE - DIRETO"): tudo no `Makefile` usa aspas, e
  o `rpmbuild` (brp add-det) não aceita espaço no buildroot, por isso `make rpm` usa um
  diretório temporário.
- **`dpkg-deb`/`makepkg` ausentes no host Fedora**: os testes de empacotamento no host pulam
  o que depende dessas ferramentas (há testes `skipped`); a verificação real é o `test-packages.sh`.
- `make dist` copia `packaging/` inteiro; arquivos de root não devem ir ao repositório (por isso
  a montagem `:ro`).

## Segurança (passada da Task 10)

Verificado e coberto por testes existentes: caminhos hostis (espaços, aspas, `$()`, `%`,
quebras de linha, URIs `file://`) no lançador, no stub, no `Exec` dos `.desktop` e no `uca.xml`;
`terminal=` nunca é executado nem "sourced" (só regex/sed de id seguro); arquivos alheios nunca são
sobrescritos nem removidos (marca `claude-aqui-managed`, `ConflictError`); `git grep` por
segredos não encontrou nada; só há stdlib + PyGObject do sistema.

Decisões registradas:

- **XML (billion laughs/XXE) no `uca.xml` local:** risco baixo (arquivo do próprio usuário,
  expat moderno limita expansão e o `ElementTree` não resolve entidades externas). Sem mudança.
- **Marca por substring:** um arquivo alheio que contenha o texto `claude-aqui-managed` é tratado
  como nosso. Improvável e inofensivo no contexto (fica no diretório do usuário). Sem mudança.
- **Modos:** scripts/stub 0755 e configs 0644; nada gravável por grupo/outros (teste
  `test_generated_files_are_never_writable_by_group_or_others`).

## Registro de bugs

### 1. `--remove-all` deixava `uca.xml` (e um `.bak`) do Thunar

- **Sintoma:** depois de ativar, desativar e remover tudo, sobravam `~/.config/Thunar/uca.xml`
  (com `<actions/>` vazio) e `uca.xml.claude-aqui.bak` (criado na reativação seguinte). Pego pelo
  `test-packages.sh`.
- **Causa:** `ThunarManager.disable` regravava o arquivo mesmo vazio; na reativação o arquivo
  vazio parecia "do usuário" e era copiado para o backup.
- **Correção:** ao desativar, se não restar nenhuma ação e não houver backup, o `uca.xml` é
  removido.
- **Teste:** `tests/managers/test_thunar.py::test_disable_removes_uca_we_created_when_nothing_is_left`
  (e `test_remove_all_deletes_every_entry_stub_and_config`, ajustado).
- **Lição:** o teste de unidade conferia só a ação, não "nada sobrou"; testes ponta a ponta de
  instalar/remover revelam resíduos.

### 2. Terminal que falha ao abrir falhava em silêncio

- **Sintoma:** com um terminal quebrado/mal configurado, clicar no item de menu não fazia nada e
  não mostrava erro.
- **Causa:** o lançador fazia `exec` do terminal; o status de saída se perdia e ninguém avisava.
- **Correção:** `run_terminal` roda o terminal sem `exec`, espera e chama `fail` se ele sair com
  status != 0 sem que o modo `--run` tenha criado o marcador `CLAUDE_AQUI_STARTED`. Terminais que
  daemonizam (status 0) e um `claude` que sai com erro depois de iniciar não geram falso erro.
- **Teste:** `test_terminal_that_exits_1_without_running_inner_reports_error`,
  `test_terminal_that_runs_inner_and_then_exits_1_is_not_a_launcher_error`,
  `test_daemonizing_terminal_returning_0_fast_is_not_an_error`.
- **Lição:** `exec` descarta o único sinal de falha que temos; o "iniciou" precisa de um canal
  próprio (marcador), não do status do terminal.

### 3. Marcador de início seguia symlink em diretório temporário (achado de segurança, MEDIUM)

- **Sintoma (revisor automático):** `: > "$CLAUDE_AQUI_STARTED"` no modo interno truncaria o alvo
  de um symlink se o diretório de estado já tivesse sido removido pelo externo e o caminho
  recriado por outro processo em `/tmp`.
- **Causa:** escrita no marcador sem validar o diretório (TOCTOU) e diretório de estado em `/tmp`
  compartilhado.
- **Correção:** estado em `$XDG_RUNTIME_DIR` (0700, por usuário) com fallback `mktemp -d` em
  `TMPDIR`; `mark_started` só escreve se o diretório se chamar `claude-aqui.*`, for real (não
  symlink), do usuário (`-O`) e `drwx------`, e cria o arquivo com `set -C` (O_EXCL: não segue nem
  sobrescreve symlink); falhas são silenciosas. O externo remove só o próprio marcador e o
  diretório (`rm -f` + `rmdir`, nunca `rm -rf`).
- **Teste:** `test_marker_symlink_to_victim_file_is_not_truncated`,
  `test_state_dir_replaced_by_symlink_does_not_touch_victim`,
  `test_state_dir_with_wide_permissions_is_not_used`, `test_marker_outside_a_claude_aqui_state_dir_is_ignored`,
  `test_state_dir_uses_xdg_runtime_dir_when_available`, `test_state_dir_falls_back_to_tmpdir_without_xdg_runtime_dir`.
- **Lição:** variável de ambiente herdada + caminho em `/tmp` = entrada não confiável; valide o
  diretório pai e use criação exclusiva.

### 4. Thunar escondia as ações padrão do sistema

- **Sintoma:** ao criar o `~/.config/Thunar/uca.xml`, as ações de `/etc/xdg/Thunar/uca.xml` sumiam
  do menu (o arquivo do usuário substitui o do sistema).
- **Causa:** o arquivo novo era criado só com a nossa ação.
- **Correção:** a raiz vem do primeiro `Thunar/uca.xml` de `$XDG_CONFIG_DIRS` (padrão `/etc/xdg`);
  `disable` remove só as nossas ações e mantém o arquivo semeado.
- **Teste:** `test_enable_seeds_new_uca_from_system_file`, `test_disable_keeps_seeded_system_actions`,
  `test_enable_without_system_seed_creates_only_our_action`, `test_existing_user_file_is_never_reseeded`.
- **Lição:** arquivos de configuração XDG em camadas: criar a camada do usuário vazia esconde as de baixo.

### 5. Nemo: ação de fundo sem `Extensions`/`Mimetypes`

- **Sintoma (provável):** o item de fundo não aparecia no Nemo.
- **Causa:** o `sample.nemo_action` do Nemo 6.x diz "EITHER EXTENSIONS OR MIMETYPES IS REQUIRED"; a
  ação `claude-aqui-bg` não tinha nenhum dos dois.
- **Correção:** `Extensions=any;` na ação de fundo (`Selection=none`).
- **Teste:** `tests/managers/test_desktop_managers.py::test_nemo_background_action_uses_selection_none`.
- **Lição:** a ausência de uma chave obrigatória era "exigida" por um teste antigo; confirme as
  chaves no exemplo do próprio programa.

### 6. `test-packages.sh` dava falso PASS para "desativado"

- **Sintoma:** um gerenciador que ficava "desativado" não reprovava a imagem.
- **Causa:** `grep -qv 'ativado'` descarta toda linha que contém "ativado", inclusive "desativado".
- **Correção:** `awk '$3 == "ativado"'` e exigência de exatamente 6 linhas; também verifica o
  código de saída de `--list-terminals`.
- **Teste:** reprodução manual com `printf 'a\tA\tdesativado\n'` (antigo: não detecta; novo: conta 0/1 de 6).
- **Lição:** filtros por substring em saída com palavras que se contêm (ativado/desativado).

### 7. `remove_all` engolia erros

- **Sintoma:** "Tudo foi removido" mesmo quando o stub ou um item não podia ser apagado.
- **Causa:** `except OSError: pass` na remoção.
- **Correção:** `RemoveReport` (falhas, backups mantidos); a CLI sai com 1 e lista os caminhos; a
  GUI mostra o mesmo texto. O `uca.xml.claude-aqui.bak` é mantido de propósito e avisado.
- **Teste:** `tests/test_service.py::test_remove_all_reports_*`, `tests/test_cli.py::test_cli_remove_all_failure_exits_1_and_lists_paths`.
- **Lição:** falha silenciosa em desinstalação é pior que falha ruidosa.

### 8. GUI: rótulo "Automático (detectado: X)" usava o terminal escolhido

- **Sintoma:** com um terminal escolhido, o rótulo "Automático" mostrava o terminal escolhido, e o
  aviso de fallback não se atualizava ao trocar de terminal.
- **Causa:** `--resolve-terminal` respeita a configuração; a GUI não chamava `refresh()` após
  `_on_terminal`.
- **Correção:** `--resolve-terminal --auto` ignora a configuração (`launcher.resolve_terminal(auto=True)`,
  `AppSnapshot.auto_terminal`); `refresh()` após a troca (sem recriar o modelo do combo, que travava o GTK).
- **Teste:** `test_resolve_terminal_auto_*`, `test_rotulo_automatico_usa_o_terminal_do_modo_automatico`,
  `test_troca_de_terminal_atualiza_o_aviso_de_fallback`.
- **Lição:** um dado de "detecção" não pode depender de uma escolha do usuário que ele pretende rotular.

### 9. Testes de pacote sujavam `dist/` e `build/`

- **Sintoma:** `dist/claude-aqui-9.9.9.tar.gz` e `build/arch/` ficavam no repositório após a suíte.
- **Causa:** `test_packaging_arch.py` rodava `make arch-src` sem `DISTDIR`/`ARCHDIR`.
- **Correção/Teste:** os diretórios vêm de `tmp_path_factory`; `ls dist build` vazio após a suíte.
- **Lição:** `.gitignore` esconde lixo de teste; verifique o disco, não só o `git status`.
