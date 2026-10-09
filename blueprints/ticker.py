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
from sqlalchemy.exc import OperationalError

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
# Telas com o aviso rodando agora ('public'/'monitor') — pra barrinha do
# telão mostrar e parar (telao.py)
_ticker_targets = set()


def init_ticker_state():
    """Chamado uma vez por create_app(), dentro de app_context — carrega o
    texto salvo do banco pro estado em memória. Tolera tabela ainda
    inexistente (banco recém-criado, antes do primeiro `flask db upgrade`
    rodar de verdade — `flask --app main db upgrade` importa main.py, e
    isso já chama create_app() antes do upgrade em si acontecer)."""
    global _ticker_text
    try:
        _ticker_text = _load_ticker_config().get('text', '')
    except OperationalError:
        db.session.rollback()


@ticker_bp.route('/api/ticker')
def ticker_api():
    return jsonify({'text': _ticker_text, 'active': _ticker_active})


@socketio.on('set_ticker')
def handle_set_ticker(data):
    global _ticker_text, _ticker_active
    _ticker_text = str(data.get('text', '')).strip()
    target = str(data.get('target', 'all'))
    _ticker_active = bool(_ticker_text)
    sent_to = {'public', 'monitor'} if target not in ('public', 'monitor') else {target}
    if _ticker_text:
        _ticker_targets.update(sent_to)
    else:
        _ticker_targets.difference_update(sent_to)
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
    # Preview no /control (não é room-scoped como o acima — o operador
    # precisa ver o texto mandado independente de qual alvo escolheu).
    emit('ticker_preview_update', payload, broadcast=True)
    import telao
    telao.broadcast_status()


@socketio.on('stop_ticker')
def handle_stop_ticker(data):
    global _ticker_active
    target = str(data.get('target', 'all'))
    if target == 'all':
        _ticker_active = False
    _ticker_targets.difference_update({'public', 'monitor'} if target not in ('public', 'monitor') else {target})
    payload = {'text': ''}
    if target == 'public':
        emit('ticker_update', payload, to='public')
    elif target == 'monitor':
        emit('ticker_update', payload, to='monitor')
    else:
        emit('ticker_update', payload, broadcast=True)
    emit('ticker_preview_update', payload, broadcast=True)
    import telao
    telao.broadcast_status()
