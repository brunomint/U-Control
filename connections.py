"""Rastreamento de clientes socketio conectados (sid -> role). Usado por
api_system_status (blueprints/utils.py) e pelos handlers de display/monitor
que ainda ficam em main.py (via _get_monitor_sids/_skip_sids, pra saber
quem excluir de um broadcast)."""
import logging

from flask import request
from flask_socketio import emit, join_room

import display_state
from extensions import socketio

logger = logging.getLogger('ucontrol')

socketio_clients_connected = 0
socketio_clients_by_sid = {}


# Evento para quando o cliente se conectar
@socketio.on('connect')
def handle_connect():
    global socketio_clients_connected
    sid = request.sid
    socketio_clients_by_sid[sid] = socketio_clients_by_sid.get(sid) or {'role': 'unknown'}
    socketio_clients_connected = len(socketio_clients_by_sid)
    logger.info('Cliente conectado')


@socketio.on('disconnect')
def handle_disconnect():
    global socketio_clients_connected
    sid = request.sid
    if sid in socketio_clients_by_sid:
        del socketio_clients_by_sid[sid]
    socketio_clients_connected = len(socketio_clients_by_sid)
    logger.info('Cliente desconectado')
    import telao
    telao.forget_client(sid)
    from blueprints import screen_share
    screen_share.forget(sid)
    from blueprints import atalhos
    atalhos.esquecer(sid)


@socketio.on('identify')
def handle_identify(data):
    sid = request.sid
    role = None
    if isinstance(data, dict):
        role = data.get('role')
    if not role:
        role = 'unknown'
    if sid not in socketio_clients_by_sid:
        socketio_clients_by_sid[sid] = {'role': role}
    else:
        socketio_clients_by_sid[sid]['role'] = role
    if role in ('public', 'monitor'):
        join_room(role)
    elif role == 'obs_overlay':
        join_room('obs')  # avisos só pra transmissão (blueprints/ticker.py)
    # Telão público, /control ou /presenter abrindo com a tela preta já ligada
    if role in ('public', 'control', 'presenter') and display_state._blackout_active:
        emit('blackout', {'active': True})


def _get_monitor_sids():
    return [sid for sid, info in socketio_clients_by_sid.items()
            if info.get('role') == 'monitor']


def _skip_sids(data):
    """Se data.exclude_monitor for true (Modo Público), retorna os sids do
    monitor de palco para excluí-los do broadcast — o monitor fica congelado."""
    return _get_monitor_sids() if data.get('exclude_monitor') else None
