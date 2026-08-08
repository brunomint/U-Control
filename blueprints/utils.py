"""Rotas utilitárias soltas: links/QR codes, relógio, ajuda, histórico,
status do sistema e download do launcher do monitor. api_culto_status
fica de fora — depende de dados de agenda, ainda não modularizados."""
import json

from flask import Blueprint, current_app, jsonify, make_response, render_template, request

import connections
from connections import socketio_clients_by_sid
from display_log import DISPLAY_LOG_PATH, load_display_log
from flask_login import login_required
from network_utils import PORTA, obter_endereco_ip

utils_bp = Blueprint('utils', __name__)


@utils_bp.route("/links")
def exibir_links():
    rotas = [
        ("/", "Controle"),
        ("monitor", "Monitor"),
        ("presenter", "Controle de Imagem"),
        ("order", "Ordem do Culto"),
        ("lyrics/display", "Monitor de Letra"),
        ("img", "Monitor de Imagem"),
        ("songs", "Biblioteca de Músicas"),
        ("bible", "Bíblia"),
        ("bible/display", "Bíblia - Display"),
        ("help", "Ajuda")
    ]
    ip_local = obter_endereco_ip()
    porta_url = f"http://{ip_local}:{PORTA}"

    dados = []
    for rota, nome in rotas:
        url = f"{porta_url}/{rota}"
        nome_arquivo = rota.replace("/", "_") + "_qr_code"
        dados.append({
            "url": url,
            "nome": nome,
            "img": f"/static/qrcodes/{nome_arquivo}.png",
            "img_id": nome_arquivo
        })

    return render_template("links.html", dados=dados)


@utils_bp.route('/download-monitor-launcher/<so>')
def download_monitor_launcher(so):
    """
    Gera um script de inicialização do monitor (/img) já com o IP/porta
    do servidor preenchidos. Abre o Chrome com autoplay liberado para que
    vídeos toquem com som automaticamente.
    Suporta: windows (.bat), linux (.sh), mac (.command)
    """
    server_host = request.host  # ex: 192.168.1.10:8585
    url = f'http://{server_host}/img'

    so = (so or '').lower()

    if so == 'windows':
        content = (
            '@echo off\r\n'
            'REM ============================================================\r\n'
            'REM  U-Control - Iniciar Monitor (Telao)\r\n'
            'REM  Abre o Chrome em modo app, com autoplay liberado (audio+video)\r\n'
            'REM ============================================================\r\n'
            '\r\n'
            f'set URL={url}\r\n'
            '\r\n'
            'set BROWSER=\r\n'
            'REM Tenta Google Chrome\r\n'
            'if exist "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'if exist "%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'if exist "%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'REM Fallback: Microsoft Edge (Chromium, aceita as mesmas flags)\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe" set BROWSER=%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe" set BROWSER=%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe\r\n'
            'REM Fallback: Brave\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" set BROWSER=%ProgramFiles%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles(x86)%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" set BROWSER=%ProgramFiles(x86)%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe\r\n'
            '\r\n'
            'if "%BROWSER%"=="" (\r\n'
            '    echo.\r\n'
            '    echo ==========================================================\r\n'
            '    echo  Nenhum navegador compativel encontrado.\r\n'
            '    echo  Instale um dos seguintes:\r\n'
            '    echo    - Google Chrome:   https://www.google.com/chrome/\r\n'
            '    echo    - Microsoft Edge:  https://www.microsoft.com/edge\r\n'
            '    echo    - Brave Browser:   https://brave.com/\r\n'
            '    echo ==========================================================\r\n'
            '    pause\r\n'
            '    exit /b 1\r\n'
            ')\r\n'
            '\r\n'
            'set PROFILE_DIR=%LocalAppData%\\UControl-Monitor\r\n'
            'start "" "%BROWSER%" --autoplay-policy=no-user-gesture-required --user-data-dir="%PROFILE_DIR%" --no-first-run --no-default-browser-check --app=%URL% --start-fullscreen\r\n'
        )
        filename = 'Iniciar-Monitor-UControl.bat'
        mimetype = 'application/octet-stream'

    elif so == 'linux':
        content = (
            '#!/bin/bash\n'
            '# ============================================================\n'
            '#  U-Control - Iniciar Monitor (Telao)\n'
            '#  Abre o Chrome em modo app, com autoplay liberado (audio+video)\n'
            '# ============================================================\n'
            '\n'
            f'URL="{url}"\n'
            '\n'
            'CHROME=""\n'
            'for c in google-chrome google-chrome-stable chromium chromium-browser brave-browser microsoft-edge microsoft-edge-stable; do\n'
            '    if command -v "$c" >/dev/null 2>&1; then\n'
            '        CHROME="$c"\n'
            '        break\n'
            '    fi\n'
            'done\n'
            '\n'
            'if [ -z "$CHROME" ]; then\n'
            '    echo ""\n'
            '    echo "=========================================================="\n'
            '    echo " Nenhum navegador compativel encontrado."\n'
            '    echo " Instale um dos seguintes:"\n'
            '    echo "   - Google Chrome:   https://www.google.com/chrome/"\n'
            '    echo "   - Chromium:        sudo apt install chromium-browser"\n'
            '    echo "   - Microsoft Edge:  https://www.microsoft.com/edge"\n'
            '    echo "   - Brave Browser:   https://brave.com/"\n'
            '    echo "=========================================================="\n'
            '    read -p "Pressione Enter para sair..."\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'PROFILE_DIR="$HOME/.config/ucontrol-monitor"\n'
            'mkdir -p "$PROFILE_DIR"\n'
            '"$CHROME" --autoplay-policy=no-user-gesture-required --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check --app="$URL" --start-fullscreen &\n'
        )
        filename = 'Iniciar-Monitor-UControl.sh'
        mimetype = 'application/x-sh'

    elif so in ('mac', 'macos', 'osx'):
        content = (
            '#!/bin/bash\n'
            '# ============================================================\n'
            '#  U-Control - Iniciar Monitor (Telao)\n'
            '#  Abre o Chrome em modo app, com autoplay liberado (audio+video)\n'
            '# ============================================================\n'
            '\n'
            f'URL="{url}"\n'
            '\n'
            'CHROME=""\n'
            'for c in \\\n'
            '    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\\n'
            '    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \\\n'
            '    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \\\n'
            '    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do\n'
            '    if [ -f "$c" ]; then\n'
            '        CHROME="$c"\n'
            '        break\n'
            '    fi\n'
            'done\n'
            '\n'
            'if [ -z "$CHROME" ]; then\n'
            '    echo ""\n'
            '    echo "=========================================================="\n'
            '    echo " Nenhum navegador compativel encontrado em /Applications."\n'
            '    echo " Instale um dos seguintes:"\n'
            '    echo "   - Google Chrome:   https://www.google.com/chrome/"\n'
            '    echo "   - Microsoft Edge:  https://www.microsoft.com/edge"\n'
            '    echo "   - Brave Browser:   https://brave.com/"\n'
            '    echo "=========================================================="\n'
            '    read -p "Pressione Enter para sair..."\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'PROFILE_DIR="$HOME/Library/Application Support/UControl-Monitor"\n'
            'mkdir -p "$PROFILE_DIR"\n'
            '"$CHROME" --autoplay-policy=no-user-gesture-required --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check --app="$URL" --start-fullscreen &\n'
        )
        filename = 'Iniciar-Monitor-UControl.command'
        mimetype = 'application/x-sh'

    else:
        return jsonify({'error': 'Sistema operacional inválido. Use: windows, linux ou mac.'}), 400

    response = make_response(content)
    response.headers['Content-Type'] = mimetype
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@utils_bp.route('/help')
def help():
    return render_template('help.html')

@utils_bp.route("/clock", methods=["GET", "POST"])
def clock():
    if request.method == "POST":
        # Handle form data here if needed
        pass

    return render_template("relogio.html")

@utils_bp.route('/historico')
@login_required
def historico():
    return render_template('historico.html')

@utils_bp.route('/api/historico')
@login_required
def api_historico():
    log = load_display_log()
    log.reverse()
    return jsonify(log)

@utils_bp.route('/api/historico', methods=['DELETE'])
@login_required
def api_historico_clear():
    try:
        with open(DISPLAY_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f)
    except Exception:
        pass
    return jsonify({'ok': True})

@utils_bp.route('/api/system/status', methods=['GET'])
@login_required
def api_system_status():
    ip_local = None
    try:
        ip_local = obter_endereco_ip()
    except Exception:
        ip_local = None

    public_url = None
    try:
        public_url = request.host_url.rstrip('/')
    except Exception:
        public_url = None

    local_url = None
    if ip_local:
        local_url = f"http://{ip_local}:{PORTA}"

    socketio_by_role = {}
    for info in socketio_clients_by_sid.values():
        role = None
        if isinstance(info, dict):
            role = info.get('role')
        if not role:
            role = 'unknown'
        socketio_by_role[role] = socketio_by_role.get(role, 0) + 1

    cpu_percent = None
    ram_percent = None
    system_stats_error = None
    try:
        import psutil
        cpu_percent = float(psutil.cpu_percent(interval=None))
        ram_percent = float(psutil.virtual_memory().percent)
    except Exception as e:
        system_stats_error = str(e)

    disk_total_gb = None
    disk_free_gb = None
    disk_used_percent = None
    disk_error = None
    try:
        import psutil
        usage = psutil.disk_usage('/')
        disk_total_gb = round(usage.total / (1024 ** 3), 1)
        disk_free_gb = round(usage.free / (1024 ** 3), 1)
        disk_used_percent = float(usage.percent)
    except Exception as e:
        disk_error = str(e)

    payload = {
        'online': True,
        'ip': ip_local,
        'port': PORTA,
        'public_url': public_url,
        'local_url': local_url,
        'socketio_clients': connections.socketio_clients_connected,
        'socketio_by_role': socketio_by_role,
        'cpu_percent': cpu_percent,
        'ram_percent': ram_percent,
        'disk_total_gb': disk_total_gb,
        'disk_free_gb': disk_free_gb,
        'disk_used_percent': disk_used_percent

    }
    if current_app.debug and system_stats_error:
        payload['system_stats_error'] = system_stats_error
    if current_app.debug and disk_error:
        payload['disk_error'] = disk_error

    return jsonify(payload)
