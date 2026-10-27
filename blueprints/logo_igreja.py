"""Logo da igreja: enviado no painel da Agenda (junto do nome da igreja) e
mostrado na "tela com logo" do telão — uma das telas neutras, ao lado da
preta e da branca (handle_blackout, static/js/telas_neutras.js).

Guardado como PNG em paths.IGREJA_DIR (entra no backup). O endereço da
imagem é público como o resto do telão: a tela pública não tem login."""
import os

from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required

import paths
from i18n import gettext as tr

logo_igreja_bp = Blueprint('logo_igreja', __name__)

MAX_BYTES = 15 * 1024 * 1024
MAX_LADO = (1920, 1080)   # maior que isso não ganha nada no projetor


def caminho_logo():
    return os.path.join(paths.IGREJA_DIR, 'logo.png')


def tem_logo():
    return os.path.isfile(caminho_logo())


@logo_igreja_bp.app_context_processor
def _tem_logo():
    return {'tem_logo_igreja': tem_logo}


@logo_igreja_bp.route('/logo-igreja.png')
def logo():
    if not tem_logo():
        return jsonify({'error': tr('Sem logo da igreja')}), 404
    return send_file(caminho_logo(), mimetype='image/png', max_age=0)


@logo_igreja_bp.route('/api/logo-igreja', methods=['POST'])
@login_required
def enviar():
    from PIL import Image, UnidentifiedImageError
    arq = request.files.get('logo')
    if not arq:
        return jsonify({'error': tr('Escolha uma imagem.')}), 400
    dados = arq.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        return jsonify({'error': tr('Imagem grande demais (máximo 15 MB).')}), 413
    import io
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except (UnidentifiedImageError, OSError):
        return jsonify({'error': tr('Esse arquivo não é uma imagem (use PNG ou JPG).')}), 400
    img = img.convert('RGBA')
    img.thumbnail(MAX_LADO)
    os.makedirs(paths.IGREJA_DIR, exist_ok=True)
    temp = caminho_logo() + '.novo'
    img.save(temp, 'PNG')
    os.replace(temp, caminho_logo())
    return jsonify({'ok': True})


@logo_igreja_bp.route('/api/logo-igreja/remover', methods=['POST'])
@login_required
def remover():
    if tem_logo():
        os.remove(caminho_logo())
    return jsonify({'ok': True})
