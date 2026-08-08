"""Avisos em ticker (texto rolando na base da tela) — estado isolado (em
memória + ticker_config.json), sem nenhuma variável compartilhada com
outra área do app (confirmado na exploração antes do split). Depende só
do utilitário compartilhado display_log."""
import json
import os

from flask import Blueprint, jsonify
from flask_socketio import emit

from display_log import append_display_log
from extensions import socketio

ticker_bp = Blueprint('ticker', __name__)

_TICKER_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ticker_config.json')


def _load_ticker_config():
    try:
        with open(_TICKER_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'text': ''}


def _save_ticker_config(text):
    try:
        with open(_TICKER_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({'text': text}, f, ensure_ascii=False)
    except Exception:
        pass


_ticker_text = _load_ticker_config().get('text', '')
_ticker_active = False  # nunca ativo no boot; exige comando explícito


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
