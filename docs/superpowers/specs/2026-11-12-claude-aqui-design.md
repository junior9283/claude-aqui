# Claude Aqui — Design

Data: 2026-11-12

## Intenção e porquê

Abrir o Claude Code numa pasta hoje exige abrir um terminal, navegar até a pasta e digitar `claude`. O app adiciona ao menu de botão direito dos gerenciadores de arquivos do Linux a ação **"Abrir Claude Code aqui"**: um clique numa pasta (ou no fundo de uma pasta aberta) abre um terminal naquela pasta com o `claude` já rodando.

O app é gráfico: detecta os gerenciadores de arquivos e terminais instalados e deixa o usuário instalar/remover o item de menu em cada um, sem editar arquivos à mão.

## Objetivos

- Item de menu "Abrir Claude Code aqui" em: Nautilus (GNOME), Dolphin (KDE), Nemo, Caja, Thunar, PCManFM-Qt.
- Interface gráfica que detecta os gerenciadores instalados, permite ativar/desativar cada um (instala/remove o item de menu) e mostra o estado atual.
- Detecção automática dos terminais instalados (gnome-terminal, konsole, kitty, alacritty, xfce4-terminal etc.), uso do padrão do desktop e escolha manual na interface.
- Distribuição em `.deb`, `.rpm` e `PKGBUILD` (Arch).
- Funciona nas principais distros (Debian/Ubuntu/Mint, Fedora/Nobara, openSUSE, Arch/Manjaro).

## Fora do escopo

- Flatpak e AppImage.
- Pastas remotas (SFTP, SMB etc.): só caminhos locais.
- Instalar o próprio Claude Code.

## Anti-objetivos (seria falha mesmo que "funcione")

- Injeção de comando por caminhos com espaços, aspas, `$`, crases ou quebras de linha: o caminho nunca é interpolado em string de shell; é passado como argumento.
- Exigir root para ligar o menu do usuário.
- Falhar em silêncio quando o `claude` não existe ou o terminal não abre.
- Alterar o navegador/terminal padrão do sistema ou outras configurações globais.

## Decisões do usuário

- App com interface gráfica, distribuído em pacotes.
- Pacotes: `.deb`, `.rpm`, Arch (`PKGBUILD`).
- Gerenciadores: Nautilus, Dolphin, Nemo, Caja, Thunar, PCManFM-Qt.
- Terminal: automático com escolha na interface.
- Ao sair do `claude`, a janela do terminal fecha. Só em caso de erro (ex.: `claude` não encontrado, pasta inválida) a janela mostra a mensagem e espera uma tecla antes de fechar.
- Alvo de distros: releases atuais com GTK4/libadwaita (Ubuntu 22.04+, Debian 12+, Mint 22+, Fedora/Nobara atuais, openSUSE Leap 15.5+, Arch). Não suportar Ubuntu 20.04, Debian 11 nem Mint 21.

## Decisões do projetista (definidas após a revisão do documento, minhas)

- **Lançador em `sh` (POSIX)**, sem Python, para abrir rápido e ter poucas dependências. Recebe o caminho como argumento (aceita também `file://` com percent-encoding e as variáveis dos scripts do Nautilus/Caja), valida que é diretório e nunca interpola o caminho em string de shell.
- **Localizar o `claude`:** procurar no PATH e, se faltar, em locais comuns (`~/.local/bin`, `~/.claude/local`, `~/.npm-global/bin`, nvm, `/usr/local/bin`, `/usr/bin`). A interface usa o mesmo critério para avisar "claude não encontrado".
- **Onde o item aparece:** só em pastas (pasta selecionada) e no fundo de uma pasta aberta. Em arquivos, o item não aparece.
- **Conflitos na instalação:** se já existir arquivo nosso no caminho, substituir; se existir arquivo que não é nosso (sem a marca do app), não sobrescrever: avisar na interface e pular esse gerenciador. `uca.xml` malformado bloqueia só o Thunar, com aviso; antes de editar, fazer cópia de segurança. Avisar para fechar o Thunar se estiver aberto.
- **Desinstalar o pacote:** o pacote não consegue limpar as pastas dos usuários. A interface oferece "Remover tudo" para fazer isso antes de desinstalar, e o item de menu verifica se o lançador ainda existe e, se não, mostra uma mensagem curta em vez de falhar em silêncio.
- **Terminal padrão:** ordem de preferência: escolha do usuário, `xdg-terminal-exec`, `x-terminal-emulator`, configuração do desktop (GNOME/KDE), lista de terminais conhecidos. Se o terminal escolhido foi desinstalado, cair no automático e avisar na interface.

## Decisões anteriores do projetista (palpites, a validar na leitura)

- **Tecnologia:** Python 3 + GTK4/libadwaita (já presente na maioria das distros, empacotamento simples).
- **Instalação do menu por usuário**, sem root, em `~/.local/share` e `~/.config`. O pacote instala o app e o lançador para todos; cada usuário liga os menus que quiser.
- **Lançador:** um executável instalado pelo pacote (ex.: `claude-aqui-launch <pasta>`), em `sh`, que resolve o terminal configurado e abre o `claude` na pasta. Todos os itens de menu chamam esse lançador.
- **Mecanismo por gerenciador:** Nautilus e Caja via scripts (`~/.local/share/nautilus/scripts`, `~/.config/caja/scripts`); Dolphin via ServiceMenu `.desktop`; Nemo via `.nemo_action`; Thunar via ação personalizada em `uca.xml`; PCManFM-Qt via ação `.desktop` em `file-manager/actions`. Para Thunar, editar o `uca.xml` preservando as ações existentes do usuário e identificando a nossa por marca própria, para remoção limpa.
- **Configuração:** arquivo do usuário em `~/.config/claude-aqui/` com o terminal escolhido; o lançador lê esse arquivo.
- **Se o `claude` não estiver no PATH:** a interface avisa; o lançador abre o terminal com mensagem explicativa em vez de fechar sozinho.
- **Se o terminal falhar ao abrir:** notificação de erro (`notify-send`/`gio`), sem travar.
- **Idioma da interface:** português (pt-BR).
- **Testes:** unitários da geração/remoção dos arquivos de menu e do lançador (inclusive caminhos hostis); verificação da instalação dos pacotes em contêineres das principais distros.

## Restrições

- Não tocar no sistema além do escopo do usuário; remoção deve devolver tudo ao estado anterior.
- Nada de `sudo`/segredos no código; nenhum dado enviado a serviços externos.

## Deixado ao construtor

- Estrutura de pastas, nomes de módulos, ícone e identidade visual.
- Formato exato dos arquivos de menu por versão de cada gerenciador.
- Ferramentas de empacotamento e CI.
- Estratégia de detecção de terminais e flags de "executar comando em pasta" de cada um.
