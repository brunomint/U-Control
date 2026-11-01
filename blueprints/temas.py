"""Página "Temas e fundos" (/temas): temas do telão do público (temas_store.py)
e os vídeos de fundo (blueprints/fundos.py).

Salvar um tema ou trocar o padrão atualiza na hora o telão que está com
letra no ar (evento tema_telao, display_public.js)."""
import json
import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

import display_state
import temas_store
from extensions import db, socketio
from i18n import gettext as tr
from models import LyricsState

temas_bp = Blueprint('temas', __name__)
logger = logging.getLogger('ucontrol')


def tema_do_payload(payload):
    """Tema resolvido para um update_lyrics (música + culto + padrão)."""
    return temas_store.resolver(payload.get('theme'), payload.get('orderDate'), payload.get('title'))


def atualizar_telao():
    """Recalcula o tema da letra que está no telão e manda pro público."""
    payload = display_state._last_lyrics_payload
    if not payload or display_state._current_display_mode != 'lyrics':
        return
    payload['tema'] = tema_do_payload(payload)
    try:
        state = LyricsState.query.first()
        if state is not None:
            state.last_payload = json.dumps(payload)
            db.session.commit()
    except Exception:
        logger.exception('temas: falha ao guardar o tema da letra no ar')
    socketio.emit('tema_telao', payload['tema'])


def avisar_biblia():
    """Manda o tema da Bíblia pras telas de /bible/display abertas."""
    socketio.emit('tema_biblia', {'tema': temas_store.tema_da_biblia()})


@temas_bp.app_context_processor
def _temas_nas_telas():
    # Para o seletor "Tema do telão" do culto (order_edit.html): só lê o banco quando a tela chama
    return {'temas_do_telao': temas_store.listar}


@temas_bp.route('/temas')
@login_required
def temas_page():
    return render_template('temas.html', fontes=list(temas_store.FONTES), fontes_css=temas_store.FONTES,
                           texto_padrao=temas_store.TEXTO_PADRAO, gradientes=temas_store.GRADIENTES,
                           transicao_padrao=temas_store.TRANSICAO_PADRAO)


@temas_bp.route('/api/temas')
@login_required
def api_listar():
    return jsonify({'temas': temas_store.listar(), 'padrao': temas_store.padrao_id(), 'biblia': temas_store.biblia_id(),
                    'texto_padrao': temas_store.TEXTO_PADRAO, 'fontes': temas_store.FONTES})


@temas_bp.route('/api/temas', methods=['POST'])
@temas_bp.route('/api/temas/<int:tema_id>', methods=['PUT'])
@login_required
def api_salvar(tema_id=None):
    data = request.get_json(silent=True) or {}
    try:
        tema = temas_store.salvar(data.get('nome'), data, tema_id)
    except ValueError:
        return jsonify({'erro': tr('Dê um nome ao tema.')}), 400
    if tema is None:
        return jsonify({'erro': tr('Tema não encontrado.')}), 404
    atualizar_telao()
    avisar_biblia()
    return jsonify({'tema': tema}), 200 if tema_id else 201


@temas_bp.route('/api/temas/<int:tema_id>', methods=['DELETE'])
@login_required
def api_apagar(tema_id):
    if not temas_store.apagar(tema_id):
        return jsonify({'erro': tr('Tema não encontrado.')}), 404
    atualizar_telao()
    avisar_biblia()
    return jsonify({'ok': True})


@temas_bp.route('/api/temas/padrao', methods=['POST'])
@login_required
def api_padrao():
    data = request.get_json(silent=True) or {}
    padrao = temas_store.definir_padrao(data.get('id'))
    atualizar_telao()
    return jsonify({'padrao': padrao})


@temas_bp.route('/api/temas/biblia')
def api_tema_biblia():
    # Sem login: quem pede é a tela da Bíblia (projetor), como /api/bible/current
    return jsonify({'tema': temas_store.tema_da_biblia()})


@temas_bp.route('/api/temas/biblia', methods=['POST'])
@login_required
def api_definir_biblia():
    data = request.get_json(silent=True) or {}
    biblia = temas_store.definir_biblia(data.get('id'))
    avisar_biblia()
    return jsonify({'biblia': biblia})
