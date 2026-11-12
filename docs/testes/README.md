# Guia de testes do Claude Aqui

## Como rodar

Testes unitários e de integração (Python, com o venv do projeto; GTK é pulado se faltar):

    .venv/bin/python -m pytest -q          # rápido
    .venv/bin/python -m pytest -v          # completo, com nomes
    .venv/bin/python -m pytest -q tests/managers/test_thunar.py   # só o que mudou

Os testes usam `HOME`/`XDG_*` em `tmp_path`: nunca tocam em `~/.config` ou `~/.local` reais.

Pacotes em contêineres (precisa de `podman`, ou `docker` como alternativa):

    scripts/test-packages.sh deb     # debian:12 e ubuntu:22.04
    scripts/test-packages.sh rpm     # fedora:latest
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
- **Flags dos terminais** (gnome-terminal, konsole, kitty, alacritty, xfce4-terminal) só são
  testadas com terminais falsos que gravam o argv; não foram validadas em terminais reais.
  xterm/x-terminal-emulator/xdg-terminal-exec recebem o caminho pelo cwd herdado, nunca no argv.
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
