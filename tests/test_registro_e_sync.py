"""Depois do culto de 01/11/2026 (dois operadores): registro de ações,
Sincronizar respeitando quem cuida do palco, rotas livres das telas neutras
e a corrida em telao.build_status."""
import logging

import pytest

import connections
import display_state
import main as ucontrol_main
import registro_acoes
import telao
from test_smoke import _operator_socket

SID_VITOR = 'sid-teste-vitor'


@pytest.fixture
def vitor_em_so_monitor():
    connections.socketio_clients_by_sid[SID_VITOR] = {'role': 'control', 'device': 'pc-vitor'}
    display_state._device_modes['pc-vitor'] = 'monitor'
    yield
    connections.socketio_clients_by_sid.pop(SID_VITOR, None)
    display_state._device_modes.pop('pc-vitor', None)


def _sync(client, aparelho):
    client.set_cookie('uc_device', aparelho)
    return client.post('/api/monitor/sync')


def test_sync_nao_mexe_no_palco_de_outro_aparelho(logged_in_client, vitor_em_so_monitor):
    telao.set_monitor('cifra', '/lyrics/display?song_id=1')
    try:
        r = _sync(logged_in_client, 'ipad-bruno')
        assert r.status_code == 409 and r.get_json()['status'] == 'palco_ocupado'
        assert telao._monitor == {'kind': 'cifra', 'url': '/lyrics/display?song_id=1'}
    finally:
        telao.set_monitor(None)


def test_quem_esta_em_so_monitor_sincroniza(logged_in_client, vitor_em_so_monitor):
    assert _sync(logged_in_client, 'pc-vitor').status_code == 200


def test_sync_volta_a_funcionar_quando_o_outro_sai(logged_in_client, vitor_em_so_monitor):
    connections.socketio_clients_by_sid.pop(SID_VITOR)
    assert _sync(logged_in_client, 'ipad-bruno').status_code == 200


def test_status_sobrevive_ao_monitor_zerado_no_meio(monkeypatch):
    real = telao.describe

    def outra_acao_zera_o_monitor(entry):
        telao.set_monitor(None)
        return real(entry)

    telao.set_monitor('cifra', '/lyrics/display')
    monkeypatch.setattr(telao, 'describe', outra_acao_zera_o_monitor)
    with ucontrol_main.app.test_request_context():
        status = telao.build_status()
    assert status['monitor']['url'] == '/lyrics/display'


def test_registro_de_evento_tem_usuario_aparelho_e_modo(app, caplog):
    caplog.set_level(logging.INFO, logger='ucontrol')
    operador = _operator_socket(app)
    operador.emit('show_image', {'image_url': '/static/imagens/a.jpg', 'exclude_monitor': True})
    linha = next(r.getMessage() for r in caplog.records if 'evento=show_image' in r.getMessage())
    assert linha.startswith('ACAO usuario=tester aparelho=')
    assert 'modo=all' in linha
    assert 'image_url=/static/imagens/a.jpg' in linha and 'exclude_monitor=True' in linha
    operador.disconnect()


def test_registro_ignora_ruido_e_nao_guarda_conteudo(app, caplog):
    caplog.set_level(logging.INFO, logger='ucontrol')
    with app.test_request_context('/'):
        registro_acoes.registrar_evento('telao_ping', ({},))
        registro_acoes.registrar_evento('update_lyrics', ({'text': 'LETRA', 'songId': 7},))
    mensagens = [r.getMessage() for r in caplog.records if r.getMessage().startswith('ACAO')]
    assert len(mensagens) == 1
    assert 'songId=7' in mensagens[0] and 'LETRA' not in mensagens[0]


def test_registro_http_tem_a_resposta(logged_in_client, caplog):
    caplog.set_level(logging.INFO, logger='ucontrol')
    _sync(logged_in_client, 'ipad-bruno')
    assert any('evento=POST /api/monitor/sync status=200' in r.getMessage()
               and 'aparelho=ipad-b' in r.getMessage() for r in caplog.records)


def test_login_nao_registra_senha(client, caplog):
    caplog.set_level(logging.INFO, logger='ucontrol')
    client.post('/login', data={'username': 'x', 'password': 'senha-secreta'})
    assert not any('senha-secreta' in r.getMessage() for r in caplog.records)


def test_falha_no_registro_nao_bloqueia_a_acao(app, monkeypatch):
    def quebra():
        raise RuntimeError('registro fora do ar')

    monkeypatch.setattr(registro_acoes, '_quem', quebra)
    with app.test_request_context('/'):
        registro_acoes.registrar_evento('blackout', ({},))
        registro_acoes.registrar_http(app.response_class())


def test_telas_neutras_so_no_telao_e_no_monitor(client):
    assert 'camada_neutra' not in client.get('/img').get_data(as_text=True)
    assert 'camada_neutra' in client.get('/lyrics/display/public').get_data(as_text=True)
    assert 'camada_neutra' in client.get('/monitor').get_data(as_text=True)
