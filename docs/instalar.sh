#!/bin/bash
# Instalador do U-Control para Linux: Ubuntu, Debian, Linux Mint e
# Raspberry Pi OS (64 bits). Servido pelo site do projeto (GitHub Pages,
# pasta docs/):
#
#   curl -fsSL https://brunomint.github.io/U-Control/instalar.sh | bash
#
# Rodar de novo atualiza para a última versão, sem apagar nada. Opções
# (depois de "bash -s --"):
#
#   --telao         abre o telão em tela cheia ao entrar na área de trabalho
#   --pasta DIR     onde instalar (padrão: ~/u-control)
#   --versao v1.2.3 instala essa versão em vez da última
#   --desinstalar   tira o serviço e o telão automático (os dados ficam)
#
# Mesmo modelo do Raspberry Pi da igreja: o código numa pasta (git), venv,
# e o ucontrol.sh rodando como serviço do systemd. Banco, fotos e áudios
# ficam dentro da pasta, fora do git (instance/, static/imagens,
# static/audio), e o git nunca mexe neles.
set -euo pipefail

REPO="brunomint/U-Control"
PORTA=8585
SERVICO="u-control"
PASTA="$HOME/u-control"
VERSAO=""
TELAO=0
DESINSTALAR=0

while [ $# -gt 0 ]; do
    case "$1" in
        --telao) TELAO=1 ;;
        --pasta) PASTA="$2"; shift ;;
        --versao) VERSAO="$2"; shift ;;
        --desinstalar) DESINSTALAR=1 ;;
        *) echo "Opção desconhecida: $1" >&2; exit 1 ;;
    esac
    shift
done

passo() { printf '\n\033[1;35m==>\033[0m \033[1m%s\033[0m\n' "$1"; }
erro() { printf '\n\033[1;31mErro:\033[0m %s\n' "$1" >&2; exit 1; }

AUTOSTART="$HOME/.config/autostart/u-control-telao.desktop"
UNIDADE="/etc/systemd/system/$SERVICO.service"
com_systemd() { [ -d /run/systemd/system ]; }

# --- desinstalar ------------------------------------------------------------

if [ "$DESINSTALAR" = 1 ]; then
    passo "Tirando o U-Control do início automático"
    if com_systemd && [ -f "$UNIDADE" ]; then
        sudo systemctl disable --now "$SERVICO" || true
        sudo rm -f "$UNIDADE"
        sudo systemctl daemon-reload
    fi
    rm -f "$AUTOSTART"
    echo "Pronto. Os dados continuam em $PASTA (músicas, cultos, fotos)."
    echo "Para apagar tudo de vez: rm -rf \"$PASTA\""
    exit 0
fi

# --- conferências -----------------------------------------------------------

[ "$(id -u)" != 0 ] || erro "rode como o seu usuário, sem sudo. O script pede a senha quando precisar."
command -v apt-get >/dev/null || erro "este instalador é para Ubuntu, Debian, Linux Mint e Raspberry Pi OS. Em outro Linux, use o Docker (veja o README)."
case "$(dpkg --print-architecture)" in
    amd64|arm64) ;;
    *) erro "precisa de um sistema de 64 bits (PC comum ou Raspberry Pi 4/5 com o Raspberry Pi OS 64 bits)." ;;
esac

passo "Instalando o que o U-Control usa (pode pedir a sua senha)"
# ffmpeg: vídeos de PowerPoint e áudio do YouTube. LibreOffice: converte
# apresentações. Carlito/Caladea/Liberation: mesmas medidas de Calibri,
# Cambria e Arial, senão o texto dos slides quebra. Pango/HarfBuzz: o
# weasyprint (PDF da ordem do culto).
sudo env DEBIAN_FRONTEND=noninteractive apt-get update -qq
# libharfbuzz-subset0 é pacote à parte só do Debian 12 / Ubuntu 24.04 em
# diante; antes vinha dentro do libharfbuzz0b
EXTRAS=""
if apt-cache show libharfbuzz-subset0 >/dev/null 2>&1; then EXTRAS="libharfbuzz-subset0"; fi
# shellcheck disable=SC2086
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    git curl ca-certificates python3 python3-venv python3-pip \
    ffmpeg libreoffice-impress \
    fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation2 \
    libpango-1.0-0 libpangoft2-1.0-0 $EXTRAS >/dev/null

# --- código -----------------------------------------------------------------

if [ -z "$VERSAO" ]; then
    VERSAO="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)"
    [ -n "$VERSAO" ] || erro "não consegui ver a última versão no GitHub. Confira a internet e tente de novo."
fi

if [ -d "$PASTA/.git" ]; then
    passo "Atualizando para a versão $VERSAO"
    # Cópia do banco antes de trocar o código (as migrations rodam na
    # próxima abertura). Guarda as 3 mais recentes.
    if [ -f "$PASTA/instance/users.db" ]; then
        mkdir -p "$PASTA/instance/backups"
        python3 - "$PASTA/instance/users.db" "$PASTA/instance/backups/antes-de-atualizar-$(date +%Y%m%d-%H%M%S).db" <<'PY'
import sqlite3, sys
origem, destino = sys.argv[1], sys.argv[2]
with sqlite3.connect(destino) as d:
    sqlite3.connect(origem).backup(d)
PY
        ls -1t "$PASTA"/instance/backups/antes-de-atualizar-*.db | tail -n +4 | xargs -r rm -f
    fi
    git -C "$PASTA" fetch -q --tags --force origin
    # -f: os QR codes (static/qrcodes) são regenerados a cada abertura e
    # ficam "modificados"; o resto que muda em uso está fora do git
    git -C "$PASTA" checkout -q -f "$VERSAO"
else
    [ ! -e "$PASTA" ] || erro "$PASTA já existe e não é uma instalação do U-Control. Use --pasta para escolher outra."
    passo "Baixando o U-Control $VERSAO"
    git clone -q "https://github.com/$REPO.git" "$PASTA"
    git -C "$PASTA" checkout -q "$VERSAO"
fi

passo "Preparando o Python (na primeira vez demora alguns minutos)"
cd "$PASTA"
# venv de outra versão do Python (o sistema foi atualizado) não serve mais
if [ -x venv/bin/python ] && ! venv/bin/python -c 'import sys' 2>/dev/null; then
    rm -rf venv
fi
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
venv/bin/python scripts/patch_flask_socketio.py >/dev/null

# --- serviço ----------------------------------------------------------------

if com_systemd; then
    passo "Deixando o U-Control ligar junto com o computador"
    sudo tee "$UNIDADE" >/dev/null <<EOF
[Unit]
Description=U-Control (projeção para igrejas)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PASTA
ExecStart=$PASTA/ucontrol.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable -q "$SERVICO"
    sudo systemctl restart "$SERVICO"

    printf 'Esperando o U-Control abrir'
    for _ in $(seq 1 60); do
        if curl -fs -o /dev/null "http://127.0.0.1:$PORTA/login"; then break; fi
        printf '.'; sleep 2
    done
    echo
    curl -fs -o /dev/null "http://127.0.0.1:$PORTA/login" \
        || erro "o U-Control não abriu. Veja o motivo com: journalctl -u $SERVICO -n 50"
fi

# Firewall do Ubuntu, se estiver ligado: libera a porta para os celulares
if command -v ufw >/dev/null && sudo ufw status 2>/dev/null | grep -q '^Status: active'; then
    sudo ufw allow "$PORTA/tcp" >/dev/null
fi

# --- telão em tela cheia (opcional) -----------------------------------------

if [ "$TELAO" = 1 ]; then
    passo "Abrindo o telão em tela cheia ao entrar na área de trabalho"
    NAVEGADOR=""
    for n in chromium chromium-browser google-chrome google-chrome-stable microsoft-edge; do
        if command -v "$n" >/dev/null; then NAVEGADOR="$n"; break; fi
    done
    if [ -z "$NAVEGADOR" ]; then
        echo "Não achei o Chromium nem o Chrome. Instale um deles e rode o instalador de novo com --telao."
    else
        mkdir -p "$(dirname "$AUTOSTART")"
        # Espera o servidor responder antes de abrir; autoplay liberado
        # para os vídeos tocarem com som, sem tocar na tela
        cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=U-Control (telão)
Exec=sh -c 'until curl -fs -o /dev/null http://127.0.0.1:$PORTA/login; do sleep 2; done; exec $NAVEGADOR --kiosk --noerrdialogs --disable-session-crashed-bubble --no-first-run --autoplay-policy=no-user-gesture-required --user-data-dir=$HOME/.config/u-control-telao http://127.0.0.1:$PORTA/img'
X-GNOME-Autostart-enabled=true
EOF
        echo "Na próxima vez que entrar na área de trabalho, o telão abre sozinho."
    fi
fi

# --- pronto -----------------------------------------------------------------

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
passo "U-Control $VERSAO instalado em $PASTA"
if com_systemd; then
    echo "Abra no navegador deste computador:  http://127.0.0.1:$PORTA"
    [ -z "$IP" ] || echo "Nos celulares da mesma rede:         http://$IP:$PORTA"
    echo
    echo "Na primeira vez, a tela de login pede para criar o primeiro usuário."
    echo "Ele liga sozinho com o computador. Para parar: sudo systemctl stop $SERVICO"
else
    echo "Este sistema não usa systemd: abra o U-Control com  $PASTA/ucontrol.sh"
fi
echo "Para atualizar, rode o mesmo comando de instalação de novo."
