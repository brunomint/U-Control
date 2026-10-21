# PyInstaller: empacota desktop.py (servidor + bandeja) numa pasta
# dist/U-Control/ com o U-Control.exe — o Inno Setup (ucontrol.iss) monta
# o instalador a partir dela. Roda no GitHub Actions
# (.github/workflows/build-windows.yml): pyinstaller windows/ucontrol.spec
#
# onedir e não onefile: o onefile descompacta ~200 MB (Bíblias, static)
# numa pasta temporária a cada abertura — lento pra abrir no culto.
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.dirname(SPECPATH)

datas = [
    (os.path.join(ROOT, 'static'), 'static'),
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'bibles'), 'bibles'),
    # env.py e versions/*.py são lidos como arquivo pelo alembic, não importados
    (os.path.join(ROOT, 'migrations'), 'migrations'),
    (os.path.join(ROOT, 'VERSION'), '.'),
]
binaries = []
hiddenimports = [
    # async_mode='threading' do Flask-SocketIO: o driver é importado por nome
    'engineio.async_drivers.threading',
    # importados só pelo migrations/env.py, que o PyInstaller não enxerga
    'logging.config',
    *collect_submodules('alembic'),
    # yt-dlp carrega os extractors por nome; weasyprint/pyphen têm dados
    *collect_submodules('yt_dlp'),
]
for pacote in ('yt_dlp_ejs', 'weasyprint', 'pyphen', 'pydyf', 'tinycss2', 'cssselect2', 'zeroconf'):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(ROOT, 'desktop.py')],
    pathex=[ROOT],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    # Só do Pi (gunicorn/eventlet) ou de desenvolvimento
    excludes=['gunicorn', 'eventlet', 'pytest', 'paramiko', 'tkinter'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='U-Control',
    icon=os.path.join(ROOT, 'static', 'U-Control-ico.ico'),
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='U-Control')
