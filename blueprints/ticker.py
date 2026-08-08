"""Avisos em ticker (texto rolando na base da tela) — estado isolado (em
memória + tabela TickerConfig), sem nenhuma variável compartilhada com
outra área do app (confirmado na exploração antes do split). Depende só
do utilitário compartilhado display_log.

O texto salvo é lido do banco uma vez na inicialização (init_ticker_state,
chamado por create_app() dentro de app_context) — não pode ser lido no
import do módulo como antes, porque isso rodava antes de
db.init_app()/app_context existirem."""
from flask import Blueprint, jsonify
from flask_socketio import emit

from display_log import append_display_log
from extensions import db, socketio
from models import TickerConfig

ticker_bp = Blueprint('ticker', __name__)


def _load_ticker_config():
    row = TickerConfig.query.first()
    return {'text': row.text or ''} if row else {'text': ''}


def _save_ticker_config(text):
    row = TickerConfig.query.first()
    if not row:
        row = TickerConfig()
        db.session.add(row)
    row.text = text
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


_ticker_text = ''
_ticker_active = False  # nunca ativo no boot; exige comando explícito


def init_ticker_state():
    """Chamado uma vez por create_app(), dentro de app_context — carrega o
    texto salvo do banco pro estado em memória."""
    global _ticker_text
    _ticker_text = _load_ticker_config().get('text', '')


@ticker_bp.route('/api/ticker')
def ticker_api():
    return jsonify({'text': _ticker_text, 'active': _ticker_active})


@socketio.on('set_ticker')
def handle_set_ticker(data):
    global _ticker_text, _ticker_active
    _ticker_text = str(data.get('text', '')).strip()
    target = str(data.get('target', 'all'))
    _ticker_active = bool(_ticker_text)
    _save_ticker_config(_ticker_text)
    if _ticker_text:
        append_display_log({'type': 'ticker', 'title': _ticker_text})
    payload = {'text': _ticker_text}
    if target == 'public':
        emit('ticker_update', payload, to='public')
    elif target == 'monitor':
        emit('ticker_update', payload, to='monitor')
    else:
        emit('ticker_update', payload, broadcast=True)


@socketio.on('stop_ticker')
def handle_stop_ticker(data):
    global _ticker_active
    target = str(data.get('target', 'all'))
    if target == 'all':
        _ticker_active = False
    payload = {'text': ''}
    if target == 'public':
        emit('ticker_update', payload, to='public')
    elif target == 'monitor':
        emit('ticker_update', payload, to='monitor')
    else:
        emit('ticker_update', payload, broadcast=True)
