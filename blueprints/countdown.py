"""Cronômetro de contagem regressiva — estado 100% isolado (em memória +
countdown_config.json), sem nenhuma variável compartilhada com outra área
do app (confirmado na exploração antes do split)."""
import json
import os
import time

from flask import Blueprint, jsonify, render_template
from flask_socketio import emit

from extensions import socketio

countdown_bp = Blueprint('countdown', __name__)

_COUNTDOWN_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'countdown_config.json')


def _load_countdown_config():
    try:
        with open(_COUNTDOWN_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'label': ''}


def _save_countdown_config(data):
    try:
        with open(_COUNTDOWN_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


_countdown_state = {
    'end_timestamp': None,
    'duration_ms': 0,
    'paused_remaining': None,
    'active': False,
    'paused': False,
    'label': _load_countdown_config().get('label', ''),
}


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


@socketio.on('pause_countdown')
def handle_pause_countdown(data):
    global _countdown_state
    if _countdown_state['active'] and not _countdown_state['paused']:
        remaining = _countdown_state['end_timestamp'] - (time.time() * 1000)
        _countdown_state['paused_remaining'] = max(0, remaining)
        _countdown_state['paused'] = True
        emit('countdown_pause', {'remaining_ms': _countdown_state['paused_remaining']}, broadcast=True)


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
