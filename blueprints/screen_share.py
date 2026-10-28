"""Relay de sinalização WebRTC pra "Tela do PC" (compartilhar a tela do
computador do operador no telão). O vídeo vai direto do navegador do
Controle pra cada tela; o servidor só repassa sdp/ice e lembra:

- quem está compartilhando e pra onde (_share) — tela que abre, recarrega
  ou reconecta no meio do compartilhamento pede e recebe sozinha;
- quem assiste (_viewers, via screen_share_hello) — telas que se
  apresentam com o papel delas: 'public', 'monitor' ou 'any' (a fonte
  "Tela do PC" do monitor dividido, que mostra em qualquer alvo).

Se o Controle que compartilha some (aba fechada, PC desligado) e não
volta em DISCONNECT_GRACE segundos, as telas param de mostrar — antes
ficavam no último quadro congelado.

O último conteúdo que vai ao ar numa tela é o que aparece: letra, Bíblia,
foto etc. tiram a Tela do PC daquela tela (tirar_da_tela, chamado por
telao.set_public/set_monitor). Antes o vídeo ficava por cima e a letra
liberada não aparecia até alguém tocar em "Parar compartilhamento"."""
import threading

from flask import request
from flask_socketio import emit

from extensions import socketio

DISCONNECT_GRACE = 15

_share = {'sid': None, 'target': None}
_viewers = {}  # sid -> 'public' | 'monitor' | 'any'
_lock = threading.Lock()


def _ve(role, target):
    return role == 'any' or target == 'all' or role == target


def _parar_tudo():
    with _lock:
        _share.update(sid=None, target=None)
        viewers = list(_viewers)
    for sid in viewers:
        socketio.emit('screen_share_stop', {}, to=sid)


def forget(sid):
    """Chamado por connections.handle_disconnect."""
    with _lock:
        _viewers.pop(sid, None)
        era_quem_compartilha = sid == _share['sid']
    if era_quem_compartilha:
        def _talvez_parar():
            socketio.sleep(DISCONNECT_GRACE)
            if _share['sid'] == sid:  # não voltou (reconectar manda start de novo)
                _parar_tudo()
        socketio.start_background_task(_talvez_parar)


def mostra_em(tela):
    """A Tela do PC está no ar em `tela` ('public' ou 'monitor')?"""
    with _lock:
        return bool(_share['sid']) and _share['target'] in ('all', tela)


def tirar_da_tela(tela):
    """Outro conteúdo foi ao ar em `tela` ('public' ou 'monitor'): a Tela
    do PC sai dela. Se não sobra tela nenhuma, o compartilhamento acaba.
    O Controle que compartilha é avisado (screen_share_tirada, com a tela
    que sobrou ou None) pra soltar a captura ou atualizar a mensagem. A
    fonte do monitor dividido (/tela-do-pc, papel 'any') é escolha à parte
    e não muda."""
    with _lock:
        alvo, quem = _share['target'], _share['sid']
        if not quem:
            return
        if alvo == 'all':
            sobra = 'monitor' if tela == 'public' else 'public'
        elif alvo == tela:
            sobra = None
        else:
            return
        if sobra:
            _share['target'] = sobra
            parar = [sid for sid, role in _viewers.items() if role == tela]
        else:
            _share.update(sid=None, target=None)
            parar = list(_viewers)
    for sid in parar:
        socketio.emit('screen_share_stop', {}, to=sid)
    # parados: as telas que saíram — o Controle fecha a conexão com elas
    socketio.emit('screen_share_tirada', {'tela': tela, 'restante': sobra, 'parados': parar}, to=quem)


@socketio.on('screen_share_hello')
def relay_screen_share_hello(data):
    role = (data or {}).get('role')
    role = role if role in ('public', 'monitor', 'any') else 'public'
    with _lock:
        _viewers[request.sid] = role
        ativo = _share['sid'] and _ve(role, _share['target'])
        payload = {'from_sid': _share['sid']}
    if ativo:
        emit('screen_share_start', payload)


@socketio.on('screen_share_start')
def relay_screen_share_start(data):
    target = (data or {}).get('target')
    target = target if target in ('public', 'monitor') else 'all'
    with _lock:
        _share.update(sid=request.sid, target=target)
        viewers = dict(_viewers)
    for sid, role in viewers.items():
        if _ve(role, target):
            emit('screen_share_start', {'from_sid': request.sid}, to=sid)
        else:
            # trocou o alvo (ex.: Ambos -> Público): o palco para de mostrar
            emit('screen_share_stop', {}, to=sid)


@socketio.on('screen_share_stop')
def relay_screen_share_stop(data):
    _parar_tudo()


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
