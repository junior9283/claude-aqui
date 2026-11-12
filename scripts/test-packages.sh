#!/usr/bin/env bash
# Testa o pacote (deb, rpm ou arch) em contêineres limpos.
#
#   scripts/test-packages.sh <deb|rpm|arch>
#
# Em cada imagem: instala as dependências de build, gera o pacote com os alvos do Makefile,
# instala, cria um usuário comum com executáveis falsos dos seis gerenciadores e confere
# --enable/--disable/--remove-all nos caminhos do usuário. Imprime PASS/FAIL por imagem e
# sai com código != 0 se qualquer imagem falhar.
#
# O repositório é montado SÓ PARA LEITURA e copiado para /tmp/work dentro do contêiner:
# nada é escrito (nem como root) na árvore do projeto nem na pasta pessoal real.
set -u

FORMAT=${1:-}
case $FORMAT in
    deb) IMAGES="docker.io/library/debian:12 docker.io/library/ubuntu:22.04" ;;
    rpm) IMAGES="registry.fedoraproject.org/fedora:latest registry.opensuse.org/opensuse/tumbleweed:latest" ;;
    arch) IMAGES="docker.io/library/archlinux:latest" ;;
    *) echo "uso: $0 <deb|rpm|arch>" >&2; exit 2 ;;
esac

if command -v podman >/dev/null 2>&1; then ENGINE=podman
elif command -v docker >/dev/null 2>&1; then ENGINE=docker
else echo "FAIL: nem podman nem docker foram encontrados." >&2; exit 2; fi

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Roda como root dentro do contêiner (FORMAT e REPO em /src vêm do ambiente).
read -r -d '' CONTAINER_SCRIPT <<'INNER'
set -eu
step() { printf '  -> %s\n' "$*"; }

step "copiando o repositório (somente leitura em /src) para /tmp/work"
mkdir -p /tmp/work
tar -C /src --exclude=./.git --exclude=./.venv --exclude=./build --exclude=./dist \
    --exclude=./.claude --exclude=__pycache__ -cf - . | tar -C /tmp/work -xf -
cd /tmp/work

step "criando usuários (tester usa o app; builder gera o pacote do Arch)"
useradd -m -s /bin/sh tester
useradd -m -s /bin/sh builder

case $FORMAT in
deb)
    export DEBIAN_FRONTEND=noninteractive
    step "dependências de build"
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends make dpkg-dev >/dev/null
    step "make deb (umask 077: o DEBIAN/ precisa continuar 0755)"
    (umask 077 && make deb >/dev/null)
    step "instalando o .deb"
    apt-get install -y -qq --no-install-recommends ./dist/claude-aqui_*_all.deb >/dev/null
    ;;
rpm)
    # Fedora usa dnf; openSUSE (Leap 16+/Tumbleweed) usa zypper e resolve as typelibs.
    if command -v zypper >/dev/null 2>&1; then
        step "dependências de build (zypper)"
        zypper -n --gpg-auto-import-keys install --no-recommends make rpm-build tar gzip shadow util-linux util-linux-systemd gawk findutils grep >/dev/null
        step "make rpm"
        make rpm >/dev/null
        step "instalando o .rpm"
        zypper -n install --allow-unsigned-rpm --no-recommends dist/claude-aqui-*.rpm >/dev/null
    else
        step "dependências de build"
        dnf install -y -q make rpm-build tar gzip >/dev/null
        step "make rpm"
        make rpm >/dev/null
        step "instalando o .rpm"
        dnf install -y -q dist/claude-aqui-*.rpm >/dev/null
    fi
    ;;
arch)
    step "dependências de build"
    pacman -Syu --noconfirm --disable-download-timeout --needed make fakeroot binutils debugedit >/dev/null
    step "make arch-src + makepkg (como usuário comum)"
    chown -R builder: /tmp/work
    su builder -c 'cd /tmp/work && make arch-src >/dev/null && cd build/arch && makepkg -f --nodeps >/dev/null'
    step "instalando o pacote"
    pacman -U --noconfirm --disable-download-timeout /tmp/work/build/arch/claude-aqui-*.pkg.tar.* >/dev/null
    ;;
esac

step "preparando o usuário de teste"
mkdir -p /home/tester/fakebin
for m in nautilus caja dolphin nemo thunar pcmanfm-qt; do
    printf '#!/bin/sh\nexit 0\n' > "/home/tester/fakebin/$m"
    chmod 755 "/home/tester/fakebin/$m"
done
chown -R tester: /home/tester/fakebin

cat > /tmp/user-test.sh <<'USER'
set -u
fails=0
ok()   { printf '     ok: %s\n' "$*"; }
fail() { printf '     ERRO: %s\n' "$*"; fails=$((fails + 1)); }
has()  { if [ -e "$1" ]; then ok "existe $1"; else fail "faltou $1"; fi; }
hasnt() { if [ -e "$1" ]; then fail "sobrou $1"; else ok "ausente $1"; fi; }
grepq() { if grep -q -- "$1" "$2" 2>/dev/null; then ok "$2 contém $1"; else fail "$2 não contém $1"; fi; }
execq() { if [ -x "$1" ]; then ok "executável $1"; else fail "não executável $1"; fi; }

D=$HOME/.local/share
C=$HOME/.config
NAUT="$D/nautilus/scripts/Abrir Claude Code aqui"
CAJA="$C/caja/scripts/Abrir Claude Code aqui"
DOLPHIN=$D/kio/servicemenus/claude-aqui.desktop
NEMO1=$D/nemo/actions/claude-aqui.nemo_action
NEMO2=$D/nemo/actions/claude-aqui-bg.nemo_action
UCA=$C/Thunar/uca.xml
PCMAN=$D/file-manager/actions/claude-aqui.desktop
STUB=$D/claude-aqui/menu-stub

echo "   [lançador]"
claude-aqui-launch --list-terminals; rc=$?
echo "     --list-terminals saiu com $rc"
[ "$rc" -eq 0 ] || fail "--list-terminals saiu com $rc"
claude-aqui-launch --find-claude; rc=$?
echo "     --find-claude saiu com $?"
[ "$rc" -le 1 ] || fail "--find-claude saiu com $rc"

echo "   [--enable all]"
claude-aqui --enable all || fail "--enable all falhou"
for f in "$NAUT" "$CAJA" "$STUB"; do has "$f"; execq "$f"; done
has "$DOLPHIN"; execq "$DOLPHIN"
has "$NEMO1"; has "$NEMO2"; has "$PCMAN"; has "$UCA"
grepq 'claude-aqui-managed' "$NAUT"
grepq 'OpenClaude' "$DOLPHIN"
grepq 'Exec=' "$NEMO1"
grepq 'claude-aqui-1' "$UCA"
grepq 'X-Action-Profile' "$PCMAN"
claude-aqui --status || fail "--status falhou"
# comparação exata ("desativado" também contém "ativado"): os 6 gerenciadores devem estar "ativado"
n=$(claude-aqui --status | awk -F'\t' '$3 == "ativado"' | wc -l)
[ "$n" -eq 6 ] && ok "6 gerenciadores ativados" || fail "esperava 6 gerenciadores ativados, achei $n"
"$STUB" --list-terminals >/dev/null || fail "o stub não repassou ao lançador"

echo "   [--disable all]"
claude-aqui --disable all || fail "--disable all falhou"
for f in "$NAUT" "$CAJA" "$DOLPHIN" "$NEMO1" "$NEMO2" "$PCMAN"; do hasnt "$f"; done
if [ -e "$UCA" ] && grep -q 'claude-aqui-' "$UCA"; then fail "a ação continua no uca.xml"; else ok "ação fora do uca.xml"; fi

echo "   [--remove-all]"
claude-aqui --enable all >/dev/null || fail "reativar falhou"
claude-aqui --remove-all || fail "--remove-all falhou"
left=$(find "$HOME/.local" "$HOME/.config" -mindepth 1 ! -type d 2>/dev/null | grep -v '^$' || true)
if [ -n "$left" ]; then fail "sobraram arquivos:"; echo "$left"; else ok "nada sobrou além de diretórios"; fi

[ "$fails" -eq 0 ]
USER
chmod 644 /tmp/user-test.sh

step "teste como usuário comum"
su tester -c 'PATH=/home/tester/fakebin:$PATH sh /tmp/user-test.sh'
INNER

overall=0
for image in $IMAGES; do
    echo "=== $FORMAT em $image"
    if "$ENGINE" run --rm --security-opt label=disable \
            -v "$REPO":/src:ro -e FORMAT="$FORMAT" \
            "$image" bash -c "$CONTAINER_SCRIPT"; then
        echo "PASS: $image"
    else
        echo "FAIL: $image"
        overall=1
    fi
done
exit $overall
