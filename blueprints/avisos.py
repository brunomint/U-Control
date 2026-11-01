"""Avisos em slides (/avisos): textos que passam sozinhos no telão do público,
em loop, com o visual de um tema (temas_store.py) e a transição dele.
Antes do culto, na oferta, nos intervalos.

O rodízio roda no próprio telão (display_public.js): o servidor manda a
lista uma vez (evento avisos_exibir) e guarda pra quem abrir ou recarregar
a tela no meio (/api/current-display). Qualquer outra coisa no telão
(letra, foto, vídeo, Bíblia) para os avisos. O palco não mostra avisos."""
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

import display_state
import temas_store
from extensions import db, socketio
from i18n import gettext as tr
from models import AvisosConfig

avisos_bp = Blueprint('avisos', __name__)

MAX_AVISOS = 50
MAX_TEXTO = 500
SEGUNDOS_PADRAO = 10


def _config():
    config = AvisosConfig.query.first()
    if config is None:
        config = AvisosConfig(itens=[], segundos=SEGUNDOS_PADRAO, embaralhar=False)
        db.session.add(config)
        db.session.commit()
    return config


def dados():
    config = _config()
    tema_id = config.tema_id if config.tema_id and temas_store.obter(config.tema_id) else None
    return {'itens': list(config.itens or []), 'tema_id': tema_id,
            'segundos': config.segundos or SEGUNDOS_PADRAO, 'embaralhar': bool(config.embaralhar)}


def salvar(data):
    config = _config()
    itens = [str(t).strip()[:MAX_TEXTO] for t in (data.get('itens') or []) if str(t or '').strip()][:MAX_AVISOS]
    try:
        segundos = max(3, min(120, int(data.get('segundos') or SEGUNDOS_PADRAO)))
    except (TypeError, ValueError):
        segundos = SEGUNDOS_PADRAO
    tema_id = data.get('tema_id')
    config.itens = itens
    config.segundos = segundos
    config.embaralhar = bool(data.get('embaralhar'))
    config.tema_id = int(tema_id) if tema_id and temas_store.obter(tema_id) else None
    db.session.commit()
    return dados()


def payload():
    d = dados()
    return {'slides': d['itens'], 'segundos': d['segundos'], 'embaralhar': d['embaralhar'],
            'tema': temas_store.resolver({'tema_id': d['tema_id']} if d['tema_id'] else None)}


def no_ar():
    return display_state._current_display_mode == 'avisos'


def atualizar_no_ar():
    """Avisos (ou o tema deles) mudaram com os avisos no telão: manda de novo."""
    if no_ar():
        display_state._avisos_payload = payload()
        socketio.emit('avisos_exibir', display_state._avisos_payload)


@avisos_bp.route('/avisos')
@login_required
def avisos_page():
    return render_template('avisos.html')


@avisos_bp.route('/api/avisos')
@login_required
def api_avisos():
    return jsonify({**dados(), 'no_ar': no_ar(), 'temas': [{'id': t['id'], 'nome': t['nome']} for t in temas_store.listar()]})


@avisos_bp.route('/api/avisos', methods=['POST'])
@login_required
def api_salvar():
    resultado = salvar(request.get_json(silent=True) or {})
    atualizar_no_ar()
    return jsonify(resultado)


@avisos_bp.route('/api/avisos/exibir', methods=['POST'])
@login_required
def api_exibir():
    import telao
    dados_avisos = payload()
    if not dados_avisos['slides']:
        return jsonify({'erro': tr('Escreva pelo menos um aviso.')}), 400
    display_state._current_display_mode = 'avisos'
    display_state._avisos_payload = dados_avisos
    socketio.emit('avisos_exibir', dados_avisos)
    telao.set_public('avisos', '/lyrics/display/public')
    telao.broadcast_status()
    return jsonify({'ok': True})


@avisos_bp.route('/api/avisos/parar', methods=['POST'])
@login_required
def api_parar():
    import telao
    if no_ar():
        display_state._current_display_mode = 'blank'
        display_state._avisos_payload = None
        socketio.emit('avisos_parar', {})
        telao.set_public('blank')
        telao.broadcast_status()
    return jsonify({'ok': True})
