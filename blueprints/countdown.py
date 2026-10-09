"""Cronômetro de contagem regressiva — estado 100% isolado (em memória +
tabela CountdownConfig), sem nenhuma variável compartilhada com outra área
do app (confirmado na exploração antes do split).

O rótulo salvo é lido do banco uma vez na inicialização (init_countdown_state,
chamado por create_app() dentro de app_context) — não pode ser lido no
import do módulo como antes (era um campo default de _countdown_state),
porque isso rodava antes de db.init_app()/app_context existirem."""
import time

from flask import Blueprint, jsonify, render_template
from flask_socketio import emit
from sqlalchemy.exc import OperationalError

from extensions import db, socketio
from models import CountdownConfig

countdown_bp = Blueprint('countdown', __name__)


def _load_countdown_config():
    row = CountdownConfig.query.first()
    return {'label': row.label or ''} if row else {'label': ''}


def _save_countdown_config(data):
    row = CountdownConfig.query.first()
    if not row:
        row = CountdownConfig()
        db.session.add(row)
    row.label = data.get('label', '')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


_countdown_state = {
    'end_timestamp': None,
    'duration_ms': 0,
    'paused_remaining': None,
    'active': False,
    'paused': False,
    'label': '',
}


def init_countdown_state():
    """Chamado uma vez por create_app(), dentro de app_context — carrega o
    rótulo salvo do banco pro estado em memória. Tolera tabela ainda
    inexistente (banco recém-criado, antes do primeiro `flask db upgrade`
    rodar de verdade — `flask --app main db upgrade` importa main.py, e
    isso já chama create_app() antes do upgrade em si acontecer)."""
    try:
        _countdown_state['label'] = _load_countdown_config().get('label', '')
    except OperationalError:
        db.session.rollback()


@countdown_bp.route('/countdown')
def countdown_page():
    return render_template('countdown.html')


@countdown_bp.route('/api/countdown/state')
def countdown_state_api():
    return jsonify(_countdown_state)


@countdown_bp.route('/api/countdown/config')
def countdown_config_api():
    return jsonify(_load_countdown_config())


@socketio.on('start_countdown')
def handle_start_countdown(data):
    global _countdown_state
    duration_ms = int(data.get('duration_seconds', 0)) * 1000
    if duration_ms <= 0:
        return
    label = str(data.get('label', '')).strip()
    _countdown_state.update({
        'end_timestamp': (time.time() * 1000) + duration_ms,
        'duration_ms': duration_ms,
        'paused_remaining': None,
        'active': True,
        'paused': False,
        'label': label,
    })
    _save_countdown_config({'label': label})
    emit('countdown_start', {
        'end_timestamp': _countdown_state['end_timestamp'],
        'duration_ms': duration_ms,
        'label': label,
    }, broadcast=True)
    import telao
    telao.broadcast_status()


@socketio.on('pause_countdown')
def handle_pause_countdown(data):
    global _countdown_state
    if _countdown_state['active'] and not _countdown_state['paused']:
        remaining = _countdown_state['end_timestamp'] - (time.time() * 1000)
        _countdown_state['paused_remaining'] = max(0, remaining)
        _countdown_state['paused'] = True
        emit('countdown_pause', {'remaining_ms': _countdown_state['paused_remaining']}, broadcast=True)
        import telao
        telao.broadcast_status()


@socketio.on('resume_countdown')
def handle_resume_countdown(data):
    global _countdown_state
    if _countdown_state['paused']:
        new_end = (time.time() * 1000) + _countdown_state['paused_remaining']
        _countdown_state.update({
            'end_timestamp': new_end,
            'paused': False,
            'paused_remaining': None,
        })
        emit('countdown_resume', {'end_timestamp': new_end}, broadcast=True)
        import telao
        telao.broadcast_status()


@socketio.on('reset_countdown')
def handle_reset_countdown(data):
    global _countdown_state
    _countdown_state.update({
        'active': False,
        'paused': False,
        'end_timestamp': None,
        'paused_remaining': None,
        'label': '',
    })
    emit('countdown_reset', {}, broadcast=True)
    import telao
    telao.broadcast_status()
