# Claude Aqui

Adiciona o item **"Abrir Claude Code aqui"** ao menu de contexto do gerenciador de
arquivos: clique com o botão direito em uma pasta (ou no fundo de uma pasta aberta) e o
terminal abre naquela pasta já executando o `claude`. Tem interface gráfica (GTK/libadwaita)
e linha de comando.

## Gerenciadores suportados

Nautilus (GNOME Files), Dolphin, Nemo, Caja, Thunar e PCManFM/PCManFM-Qt.

Observações importantes:

- **Nautilus e Caja (desvio da spec):** só permitem *scripts*, que aparecem no submenu
  **Scripts** e **também em arquivos**; não dá para restringir a pastas sem a extensão
  `python3-nautilus`/`caja-python` (dependência extra). Ao receber um arquivo, o script
  mostra "Selecione uma pasta." e não faz nada.
- **Thunar (a validar):** a ação personalizada usa `%f`; ainda não foi confirmado que `%f`
  funcione no fundo da pasta (clique no espaço vazio). Validar em um Thunar real.
- **Nemo e libfm/PCManFM (a validar):** as chaves usadas nos arquivos `.nemo_action` e de
  menu do libfm ainda precisam ser confirmadas em um gerenciador real.
- Nos demais gerenciadores o item aparece só em pastas e no fundo de pasta aberta.

## Distribuições-alvo

Ubuntu 22.04+, Debian 12+, Linux Mint 22+, Fedora e Nobara atuais, openSUSE Leap 15.5+ e Arch.

## Instalação

Pelos pacotes (deb, rpm, PKGBUILD): veja `packaging/`.

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
    claude-aqui --remove-all        # remove tudo que o app criou

Sem argumentos abre a interface gráfica.

## Desinstalar

**Antes de desinstalar o pacote, use "Remover tudo"** na interface (ou
`claude-aqui --remove-all`): os itens de menu ficam na sua pasta pessoal e o gerenciador de
pacotes não os remove.
