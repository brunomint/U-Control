"""U-Control como programa de computador (o .exe do instalador Windows):
servidor + ícone na bandeja + telas abertas em janela própria, no estilo
do Holyrics.

O servidor é o mesmo do Pi: escuta em 0.0.0.0, então celular, tablet e
outros PCs da rede continuam usando pelo navegador. A diferença é só o
que fica em volta dele:
- os dados vão pra %APPDATA%\\U-Control (ver paths.py) — a pasta do
  programa é trocada inteira a cada atualização;
- as migrations rodam na abertura (no Pi quem faz é o deploy, no Docker
  o docker-entrypoint.sh);
- abrir de novo com o programa já rodando só abre o Controle;
- o menu da bandeja abre as telas (telão, letra pública, palco) em
  janela de app do Chrome/Edge, em tela cheia no segundo monitor.

Também roda fora do Windows (python desktop.py) — sem pystray instalado
fica só o servidor, sem bandeja."""
import os
import sys

# No .exe, sys.executable é este programa: cifras.py roda o yt-dlp como
# "<python> -m yt_dlp ...", e sem isto abriria outro U-Control
if sys.argv[1:3] == ['-m', 'yt_dlp']:
    import yt_dlp
    sys.exit(yt_dlp.main(sys.argv[3:]))

if sys.platform == 'win32' and not os.environ.get('UCONTROL_DATA_DIR'):
    os.environ['UCONTROL_DATA_DIR'] = os.path.join(os.environ['APPDATA'], 'U-Control')
os.environ.setdefault('UCONTROL_NO_BROWSER', '1')

import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import webbrowser  # noqa: E402

from network_utils import PORTA, obter_endereco_ip  # noqa: E402

LOCAL = f'http://127.0.0.1:{PORTA}'


def _ja_rodando():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', PORTA)) == 0


def _saida_sem_console():
    # .exe sem janela de console: sys.stdout/stderr são None e qualquer
    # write() de biblioteca quebra — manda tudo pro arquivo
    if sys.stdout is None or sys.stderr is None:
        import paths
        pasta = paths.DATA_DIR or os.path.join(paths.APP_DIR, 'instance')
        os.makedirs(pasta, exist_ok=True)
        log = open(os.path.join(pasta, 'console.log'), 'a', buffering=1, encoding='utf-8')
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def _ffmpeg_no_path():
    # O instalador traz o ffmpeg.exe em bin\ ao lado do U-Control.exe
    # (gallery.py e o yt-dlp procuram no PATH). No .exe, paths.APP_DIR é
    # a _internal\ do PyInstaller — a pasta do programa é a do executável.
    import paths
    programa = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else paths.APP_DIR
    pasta = os.path.join(programa, 'bin')
    if os.path.isdir(pasta):
        os.environ['PATH'] = pasta + os.pathsep + os.environ.get('PATH', '')


# --- Telas -----------------------------------------------------------------

def _navegador():
    """Chrome/Edge/Brave, na mesma ordem do script de /download-monitor-launcher."""
    if sys.platform != 'win32':
        for nome in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
                     'brave-browser', 'microsoft-edge', 'microsoft-edge-stable'):
            if shutil.which(nome):
                return shutil.which(nome)
        return None
    for base, rel in (
        ('ProgramFiles', r'Google\Chrome\Application\chrome.exe'),
        ('ProgramFiles(x86)', r'Google\Chrome\Application\chrome.exe'),
        ('LocalAppData', r'Google\Chrome\Application\chrome.exe'),
        ('ProgramFiles', r'Microsoft\Edge\Application\msedge.exe'),
        ('ProgramFiles(x86)', r'Microsoft\Edge\Application\msedge.exe'),
        ('ProgramFiles', r'BraveSoftware\Brave-Browser\Application\brave.exe'),
        ('ProgramFiles(x86)', r'BraveSoftware\Brave-Browser\Application\brave.exe'),
    ):
        caminho = os.path.join(os.environ.get(base, ''), rel)
        if os.path.isfile(caminho):
            return caminho
    return None


def _monitor_secundario():
    """(x, y) do canto do primeiro monitor que não é o principal — o
    datashow. None com um monitor só (ou fora do Windows)."""
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

    achados = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def _cada(hmon, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        if not info.dwFlags & 1:  # MONITORINFOF_PRIMARY
            achados.append((info.rcMonitor.left, info.rcMonitor.top))
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_cada), 0)
    return achados[0] if achados else None


def abrir_tela(chave):
    """Abre uma das telas de LAUNCHER_TELAS em janela de app, com autoplay
    liberado (vídeo com som) — mesmas flags e mesmo perfil por tela do
    script baixável, então a janela lembra o lugar dela nos dois."""
    from blueprints.utils import LAUNCHER_TELAS
    tela = LAUNCHER_TELAS[chave]
    url = LOCAL + tela['path']
    navegador = _navegador()
    if not navegador:
        webbrowser.open(url)
        return
    base = os.environ.get('LocalAppData') or os.path.expanduser('~/.config')
    args = [navegador, f'--user-data-dir={os.path.join(base, "UControl-" + tela["perfil"])}',
            f'--app={url}', '--autoplay-policy=no-user-gesture-required',
            '--no-first-run', '--no-default-browser-check']
    posicao = _monitor_secundario()
    if posicao:
        args += [f'--window-position={posicao[0]},{posicao[1]}', '--start-fullscreen']
    subprocess.Popen(args)


def abrir_controle():
    webbrowser.open(LOCAL + '/control')


# --- Servidor --------------------------------------------------------------

def _preparar_banco(app):
    import paths
    from flask_migrate import upgrade
    with app.app_context():
        upgrade(directory=paths.MIGRATIONS_DIR)


def _iniciar_servidor():
    import main
    _preparar_banco(main.app)
    threading.Thread(
        target=main.socketio.run, args=(main.app,), daemon=True,
        kwargs=dict(host='0.0.0.0', port=PORTA, use_reloader=False, allow_unsafe_werkzeug=True),
    ).start()
    for _ in range(100):
        if _ja_rodando():
            return
        time.sleep(0.1)


def _bandeja():
    try:
        import pystray
        from PIL import Image
    except ImportError:
        return None
    import paths

    def item(texto, acao, **kw):
        return pystray.MenuItem(texto, lambda _icon, _item: acao(), **kw)

    def sair(icon, _item):
        icon.stop()

    endereco = f'Na rede: http://{obter_endereco_ip()}:{PORTA}'
    itens = [
        item('Abrir Controle', abrir_controle, default=True),
        pystray.Menu.SEPARATOR,
        item('Telão (imagens e vídeos)', lambda: abrir_tela('img')),
        item('Tela pública de letras', lambda: abrir_tela('publico')),
        item('Retorno de palco', lambda: abrir_tela('palco')),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(endereco, None, enabled=False),
        item('Links e QR codes para celular', lambda: webbrowser.open(LOCAL + '/links')),
    ]
    if sys.platform == 'win32':
        itens.append(item('Abrir pasta de dados', lambda: os.startfile(paths.DATA_DIR)))
    itens += [pystray.Menu.SEPARATOR, pystray.MenuItem('Sair', sair)]
    imagem = Image.open(os.path.join(paths.APP_DIR, 'static', 'U-Control_Icon.png'))
    return pystray.Icon('U-Control', imagem, 'U-Control', pystray.Menu(*itens))


def run():
    if _ja_rodando():
        abrir_controle()
        return
    _saida_sem_console()
    _ffmpeg_no_path()
    _iniciar_servidor()
    abrir_controle()
    try:
        icone = _bandeja()
        if icone:
            icone.run()  # bloqueia até "Sair"
            # threads do servidor (socket.io, timers) não podem segurar o
            # processo aberto depois de "Sair"
            os._exit(0)
    except Exception:
        # Sem área de trabalho (serviço, máquina de build) a bandeja
        # falha — o servidor segue no ar mesmo assim
        import logging
        logging.getLogger('ucontrol').exception('Bandeja indisponível; só o servidor')
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    run()
