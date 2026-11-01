"""Vídeos de fundo do telão (tema da letra, botão "Tema" em /lyrics/<id>).

Ficam na pasta "Fundos" da galeria. O vídeo enviado é convertido pelo
ffmpeg, com prioridade baixa, para H.264 sem som, 30 fps, no máximo
1920x1080 (1280x720 no Raspberry Pi): leve pra tocar em loop atrás da
letra sem travar o telão. Enquanto converte, o nome aparece em
"convertendo" e o arquivo só entra na pasta quando termina.
"""
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import threading

from flask import Blueprint, jsonify, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from i18n import gettext as tr
from paths import IMAGE_FOLDER

fundos_bp = Blueprint('fundos', __name__)

PASTA = 'Fundos'
EXTENSOES = ('.mp4', '.m4v', '.mov', '.webm', '.mkv', '.avi', '.wmv', '.mpg', '.mpeg', '.flv', '.3gp')
_convertendo = set()
_lock = threading.Lock()


def _pasta():
    return os.path.join(IMAGE_FOLDER, PASTA)


def _no_pi():
    return platform.machine().lower() in ('aarch64', 'arm64', 'armv7l', 'armv6l') and os.name != 'nt'


def _env():
    # O serviço do Pi roda com PATH só do venv; no Windows o desktop.py já põe o ffmpeg do instalador no PATH
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join(filter(None, [env.get('PATH'), '/usr/local/bin', '/usr/bin', '/bin']))
    return env


def _ffmpeg():
    return shutil.which('ffmpeg', path=_env().get('PATH'))


def comando_ffmpeg(ffmpeg, origem, destino, no_pi=None):
    largura, altura = (1280, 720) if (_no_pi() if no_pi is None else no_pi) else (1920, 1080)
    nice = shutil.which('nice', path='/usr/bin:/bin')
    return ([nice, '-n', '19'] if nice else []) + [
        ffmpeg, '-y', '-loglevel', 'error', '-threads', '2', '-i', origem, '-an',
        '-vf', f"scale='min({largura},iw)':'min({altura},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30",
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', destino,
    ]


def _converter(origem, tmp_dir, nome):
    destino_final = os.path.join(_pasta(), nome + '.mp4')
    parcial = os.path.join(tmp_dir, 'saida.mp4')
    try:
        proc = subprocess.run(comando_ffmpeg(_ffmpeg(), origem, parcial), capture_output=True, timeout=3600, env=_env())
        if proc.returncode != 0 or not os.path.exists(parcial):
            logging.error("fundos: ffmpeg não converteu %s: %s", nome, proc.stderr[-300:].decode(errors='replace'))
            return
        os.makedirs(_pasta(), exist_ok=True)
        shutil.move(parcial, destino_final)
    except Exception:
        logging.exception("fundos: falha convertendo %s", nome)
    finally:
        with _lock:
            _convertendo.discard(nome)
        shutil.rmtree(tmp_dir, ignore_errors=True)


@fundos_bp.route('/api/fundos')
@login_required
def listar_fundos():
    pasta = _pasta()
    videos = []
    if os.path.isdir(pasta):
        for f in sorted(os.listdir(pasta), key=str.lower):
            if f.lower().endswith(('.mp4', '.webm', '.mov', '.m4v')) and os.path.isfile(os.path.join(pasta, f)):
                videos.append({'url': f'/static/imagens/{PASTA}/{f}', 'nome': os.path.splitext(f)[0]})
    with _lock:
        convertendo = sorted(_convertendo)
    return jsonify({'videos': videos, 'convertendo': convertendo, 'ffmpeg': bool(_ffmpeg())})


@fundos_bp.route('/api/fundos', methods=['POST'])
@login_required
def enviar_fundo():
    arquivo = request.files.get('video')
    nome_original = secure_filename(arquivo.filename) if arquivo and arquivo.filename else ''
    base, ext = os.path.splitext(nome_original)
    if not base or ext.lower() not in EXTENSOES:
        return jsonify({'ok': False, 'erro': tr('Envie um vídeo (MP4, MOV, WEBM, MKV ou AVI).')}), 400
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        return jsonify({'ok': False, 'erro': tr('Falta o ffmpeg neste computador para preparar o vídeo de fundo.')}), 400
    nome = base
    n = 2
    with _lock:
        while nome in _convertendo or os.path.exists(os.path.join(_pasta(), nome + '.mp4')):
            nome = f'{base}-{n}'
            n += 1
        _convertendo.add(nome)
    tmp_dir = tempfile.mkdtemp(prefix='ucontrol-fundo-')
    origem = os.path.join(tmp_dir, 'origem' + ext.lower())
    arquivo.save(origem)
    threading.Thread(target=_converter, args=(origem, tmp_dir, nome), daemon=True).start()
    return jsonify({'ok': True, 'nome': nome}), 202
