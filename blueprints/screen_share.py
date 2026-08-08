"""Relay de sinalização WebRTC pra compartilhamento de tela — puro repasse
de mensagens entre clientes (sdp/ice candidates), zero estado
compartilhado com o resto do núcleo de display."""
from flask import request
from flask_socketio import emit

from extensions import socketio


@socketio.on('screen_share_start')
def relay_screen_share_start(data):
    target = data.get('target', 'all')
    payload = {'from_sid': request.sid}
    if target == 'public':    emit('screen_share_start', payload, to='public')
    elif target == 'monitor': emit('screen_share_start', payload, to='monitor')
    else:                     emit('screen_share_start', payload, broadcast=True)

@socketio.on('screen_share_stop')
def relay_screen_share_stop(data):
    emit('screen_share_stop', {}, broadcast=True)

@socketio.on('screen_share_request')
def relay_screen_share_request(data):
    emit('screen_share_request', {'from_sid': request.sid}, to=data['broadcaster_sid'])

@socketio.on('screen_share_offer')
def relay_screen_share_offer(data):
    emit('screen_share_offer', {'sdp': data['sdp'], 'from_sid': request.sid}, to=data['target_sid'])

@socketio.on('screen_share_answer')
def relay_screen_share_answer(data):
    emit('screen_share_answer', {'sdp': data['sdp'], 'from_sid': request.sid}, to=data['target_sid'])

@socketio.on('screen_share_ice')
def relay_screen_share_ice(data):
    emit('screen_share_ice', {'candidate': data['candidate'], 'from_sid': request.sid}, to=data['target_sid'])
