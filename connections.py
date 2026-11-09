"""Rastreamento de clientes socketio conectados (sid -> role). Usado por
api_system_status (blueprints/utils.py) e pelos handlers de display/monitor
que ainda ficam em main.py (via _get_monitor_sids/_skip_sids, pra saber
quem excluir de um broadcast)."""
import logging

from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room

import display_state
from extensions import socketio

logger = logging.getLogger('ucontrol')

socketio_clients_connected = 0
socketio_clients_by_sid = {}


def sala_do_aparelho(device=None):
    """Sala Socket.IO com todas as abas de um aparelho (cookie uc_device):
    o que é só dele — preparado, acompanhar ao vivo — vai pra ela."""
    return f'aparelho:{display_state.current_device() if device is None else device}'


# Evento para quando o cliente se conectar
@socketio.on('connect')
def handle_connect():
    global socketio_clients_connected
    sid = request.sid
    socketio_clients_by_sid[sid] = socketio_clients_by_sid.get(sid) or {'role': 'unknown'}
    # Máquina desta conexão (cookie uc_device): pra saber se OUTRO PC
    # conectado cuida do palco (display_state.palco_de_outro_pc)
    device = request.cookies.get('uc_device') or ''
    socketio_clients_by_sid[sid]['device'] = device
    socketio_clients_by_sid[sid]['usuario'] = current_user.username if current_user.is_authenticated else ''
    join_room(sala_do_aparelho(device))
    socketio_clients_connected = len(socketio_clients_by_sid)
    # Voltou (outra aba, Wi-Fi caiu) com um modo guardado de tela que
    # outra pessoa pegou nesse meio-tempo: larga essa tela (destinos.py)
    import destinos
    destinos.ajustar_ao_conectar(device, socketio_clients_by_sid[sid]['usuario'])
    logger.info('Cliente conectado')


@socketio.on('disconnect')
def handle_disconnect():
    global socketio_clients_connected
    sid = request.sid
    import destinos
    import telao
    donos_antes = destinos.donos()
    if sid in socketio_clients_by_sid:
        del socketio_clients_by_sid[sid]
    socketio_clients_connected = len(socketio_clients_by_sid)
    logger.info('Cliente desconectado')
    telao.forget_client(sid)
    # Fechou o último Controle de quem cuidava de uma tela: ela fica livre,
    # e os outros aparelhos precisam ver isso já (antes ficava "com Bruno"
    # até a próxima ação — teste de 09/11)
    if destinos.donos() != donos_antes:
        telao.broadcast_status()
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
    # Telão, monitor, /control ou /presenter abrindo com uma tela neutra
    # (preta/branca/logo) já ligada em alguma tela
    if role in ('public', 'monitor', 'control', 'presenter') and any(display_state._telas_neutras.values()):
        emit('blackout', display_state.blackout_payload())


def _get_monitor_sids():
    return [sid for sid, info in socketio_clients_by_sid.items()
            if info.get('role') == 'monitor']


def _skip_sids(data):
    """Se data.exclude_monitor for true (Modo Público), retorna os sids do
    monitor de palco para excluí-los do broadcast — o monitor fica congelado."""
    return _get_monitor_sids() if data.get('exclude_monitor') else None
