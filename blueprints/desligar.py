"""Desligar o U-Control pelo site, como fechar o Holyrics (só na instalação
Windows, ver desktop_ponte.py). Só no próprio computador do U-Control:
pelo celular ou por outro PC o botão não aparece, pra ninguém apagar o
telão no meio do culto sem querer."""
from flask import Blueprint, abort, jsonify, render_template
from flask_login import login_required

import desktop_ponte
from i18n import gettext as _
from blueprints.utils import _pedido_local

desligar_bp = Blueprint('desligar', __name__)


def _pode():
    return desktop_ponte.pode_desligar() and _pedido_local()


@desligar_bp.app_context_processor
def _menu():
    # _nav.html mostra "Desligar o U-Control" no menu Sistema
    return {'pode_desligar': _pode}


@desligar_bp.route('/desligar')
@login_required
def desligar_page():
    if not _pode():
        abort(404)
    return render_template('desligar.html')


@desligar_bp.route('/api/desligar', methods=['POST'])
@login_required
def api_desligar():
    if not _pode():
        return jsonify({'error': _('Desligue pelo computador onde o U-Control está rodando.')}), 403
    desktop_ponte.desligar()
    return jsonify({'ok': True})
