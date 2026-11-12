# Claude Aqui

Adiciona o item **"Abrir Claude Code aqui"** ao menu de contexto do gerenciador de
arquivos: clique com o botão direito em uma pasta (ou no fundo de uma pasta aberta) e o
terminal abre naquela pasta já executando o `claude`. Tem interface gráfica (GTK/libadwaita)
e linha de comando.

## Gerenciadores suportados

Nautilus (GNOME Files), Dolphin, Nemo, Caja, Thunar e PCManFM-Qt (`pcmanfm-qt`; o PCManFM em GTK não é detectado).

Observações importantes:

- **Nautilus e Caja (desvio da spec):** só permitem *scripts*, que aparecem no submenu
  **Scripts** e **também em arquivos**; não dá para restringir a pastas sem a extensão
  `python3-nautilus`/`caja-python` (dependência extra). Ao receber um arquivo, o script
  mostra "Selecione uma pasta." e não faz nada.
- **Thunar (a validar):** a ação personalizada usa `%f`; ainda não foi confirmado que `%f`
  funcione no fundo da pasta (clique no espaço vazio). Validar em um Thunar real.
- **Nemo:** as chaves foram conferidas com o `sample.nemo_action` do Nemo 6.x (a ação de
  fundo usa `Selection=none` e `Extensions=any;`, pois o Nemo exige `Extensions` ou
  `Mimetypes`); falta só ver o item no menu de um Nemo real.
- **PCManFM-Qt/libfm (a validar):** as chaves do menu do libfm ainda precisam ser
  confirmadas em um gerenciador real.
- **Thunar:** ao criar o `uca.xml` do usuário, o app parte das ações padrão do sistema
  (`Thunar/uca.xml` em `$XDG_CONFIG_DIRS`, padrão `/etc/xdg`) para não escondê-las.
- Nos demais gerenciadores o item aparece só em pastas e no fundo de pasta aberta.

## Distribuições-alvo

Ubuntu 22.04+, Debian 12+, Linux Mint 22+, Fedora e Nobara atuais, **openSUSE Leap 16+ e
Tumbleweed** e Arch. O openSUSE Leap 15.x **não é suportado**: o `python3` dele é o 3.6.

Requer **Python 3.9 ou mais novo** (o código usa `ET.indent`, `unlink(missing_ok=)` e
`from __future__ import annotations`); os três pacotes declaram essa dependência.

Terminais reconhecidos (modo automático): `xdg-terminal-exec`, `x-terminal-emulator`, o
terminal padrão do desktop (gsettings no GNOME, kreadconfig no KDE) e, por prioridade,
gnome-terminal, konsole, kitty, alacritty, xfce4-terminal, xterm e os acrescentados nesta
versão (ver `claude-aqui-launch --list-terminals`). Se o terminal falhar ao abrir, o
lançador mostra um aviso em vez de falhar em silêncio.

## Instalação

Pelos pacotes (veja `packaging/`):

    make deb                          # dist/claude-aqui_VERSÃO_all.deb (precisa de dpkg-deb)
    make rpm                          # dist/claude-aqui-VERSÃO-1*.noarch.rpm (precisa de rpmbuild)
    make arch-src                     # build/arch/ com PKGBUILD + tarball; depois: cd build/arch && makepkg
    scripts/test-packages.sh deb|rpm|arch   # constrói, instala e testa em contêineres podman/docker

`scripts/test-packages.sh` testa deb (Debian 12, Ubuntu 22.04), rpm (Fedora e openSUSE
Tumbleweed) e arch, imprimindo PASS/FAIL por imagem. O repositório é montado só para leitura.

A partir do código-fonte:

    sudo make install                 # PREFIX=/usr por padrão
    make install PREFIX=$HOME/.local  # instalação só para o usuário
    make uninstall                    # remove tudo o que o install criou
    make dist VERSION=1.0.0           # gera dist/claude-aqui-1.0.0.tar.gz

`DESTDIR` é respeitado (útil para empacotar). O caminho do lançador
(`$(PREFIX)/bin/claude-aqui-launch`) e o diretório da biblioteca são ajustados na cópia
instalada para qualquer `PREFIX`.

## Uso

Abra **Claude Aqui** no menu de aplicativos e ative os gerenciadores desejados, ou use a CLI:

    claude-aqui --status            # estado de cada gerenciador
    claude-aqui --enable ID|all     # ativa o item de menu
    claude-aqui --disable ID|all    # desativa o item de menu
    claude-aqui --remove-all        # remove tudo que o app criou (sai com 1 e lista o que não pôde ser removido)

Sem argumentos abre a interface gráfica.

## Desinstalar

**Antes de desinstalar o pacote, use "Remover tudo"** na interface (ou
`claude-aqui --remove-all`): os itens de menu ficam na sua pasta pessoal e o gerenciador de
pacotes não os remove.

O `~/.config/Thunar/uca.xml.claude-aqui.bak` (cópia do seu `uca.xml` antes da primeira edição)
é **mantido de propósito**, mesmo no "Remover tudo", para não apagar dados seus; o app avisa
o caminho. Apague-o à mão se não precisar mais dele.
