"""Quem cuida de cada tela (destinos.py) — o culto de 08/11/2026: o PC do
Vitor em "Os dois" passava por cima do iPad do Bruno no público e no site."""
import pytest

import connections
import display_state
import destinos
import telao
from test_smoke import _operator_socket


@pytest.fixture(autouse=True)
def padrao_de_verdade():
    """Aqui vale o padrão real: aparelho novo sem tela nenhuma."""
    display_state.MODO_INICIAL = 'none'
    yield


@pytest.fixture
def bruno_e_vitor(app):
    bruno, vitor = _operator_socket(app, 'bruno'), _operator_socket(app, 'vitor')
    ds = list(connections.socketio_clients_by_sid.values())
    yield bruno, vitor, ds[-2]['device'], ds[-1]['device']
    for s in (bruno, vitor):
        s.disconnect()
    telao.set_monitor(None)
    telao.set_public('clock', '/clock')   # as fotos destes testes não ficam "no ar" pros seguintes


def _recusas(sock):
    return [m['args'][0]['motivo'] for m in sock.get_received() if m['name'] == 'acao_recusada']


def _foto(sock, nome):
    sock.emit('show_image', {'image_url': f'/static/imagens/{nome}.jpg', 'use_active_mode': True})


def test_aparelho_novo_nao_mexe_em_tela_nenhuma(bruno_e_vitor):
    bruno, vitor, d_bruno, _ = bruno_e_vitor
    assert display_state.device_mode(d_bruno) == 'none'
    antes = display_state._last_image_url
    _foto(bruno, 'nova')
    assert display_state._last_image_url == antes
    assert any('Escolha' in m for m in _recusas(bruno))


def test_quem_escolhe_uma_tela_livre_fica_com_ela(bruno_e_vitor):
    bruno, vitor, d_bruno, d_vitor = bruno_e_vitor
    assert bruno.emit('set_display_mode', {'mode': 'public'}, callback=True)['ok']
    assert vitor.emit('set_display_mode', {'mode': 'monitor'}, callback=True)['ok']
    assert destinos.donos() == {'public': 'bruno', 'monitor': 'vitor'}
    _foto(bruno, 'do-bruno')
    assert display_state._last_image_url == '/static/imagens/do-bruno.jpg'


def test_os_dois_nao_passa_por_cima_de_quem_cuida(bruno_e_vitor):
    """O caso de 08/11: Vitor em "Os dois" trocava o público do Bruno."""
    bruno, vitor, d_bruno, d_vitor = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    r = vitor.emit('set_display_mode', {'mode': 'all'}, callback=True)
    assert r == {'ok': False, 'ocupadas': {'public': 'bruno'}}
    assert display_state.device_mode(d_vitor) == 'none'
    _foto(bruno, 'do-bruno')
    _foto(vitor, 'do-vitor')
    assert display_state._last_image_url == '/static/imagens/do-bruno.jpg'
    assert _recusas(vitor)   # recusado (ele ficou sem tela)


def test_tela_preta_de_um_nao_cobre_a_tela_do_outro(bruno_e_vitor):
    bruno, vitor, _, _ = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    vitor.emit('blackout', {'tipo': 'preta', 'active': True, 'usar_modo': True})
    try:
        assert display_state._telas_neutras == {'public': None, 'monitor': 'preta'}
    finally:
        vitor.emit('blackout', {'tipo': 'preta', 'active': False, 'usar_modo': True})


def test_assumir_tira_a_tela_de_quem_tinha(bruno_e_vitor):
    bruno, vitor, d_bruno, d_vitor = bruno_e_vitor
    vitor.emit('set_display_mode', {'mode': 'all'})
    vitor.get_received()
    r = bruno.emit('assumir_tela', {'tela': 'public'}, callback=True)
    assert r['ok']
    assert destinos.donos() == {'public': 'bruno', 'monitor': 'vitor'}
    assert display_state.device_mode(d_bruno) == 'public'
    assert display_state.device_mode(d_vitor) == 'monitor'   # Vitor fica só com o palco
    assert any(m['name'] == 'tela_assumida' and m['args'][0]['por'] == 'bruno' for m in vitor.get_received())


def test_mesma_pessoa_em_varios_aparelhos_nao_se_bloqueia(app):
    """O mesmo login no PC e no celular é a mesma pessoa."""
    pc, cel = _operator_socket(app, 'vitor'), _operator_socket(app, 'vitor')
    try:
        assert pc.emit('set_display_mode', {'mode': 'monitor'}, callback=True)['ok']
        assert cel.emit('set_display_mode', {'mode': 'monitor'}, callback=True)['ok']
        assert not _recusas(cel)
    finally:
        pc.disconnect(); cel.disconnect()


def test_tela_fica_livre_quando_o_responsavel_sai(bruno_e_vitor):
    bruno, vitor, _, d_vitor = bruno_e_vitor
    vitor.emit('set_display_mode', {'mode': 'public'})
    for sid, info in list(connections.socketio_clients_by_sid.items()):
        if info['device'] == d_vitor:
            del connections.socketio_clients_by_sid[sid]
    assert destinos.dono('public') is None
    assert bruno.emit('set_display_mode', {'mode': 'public'}, callback=True)['ok']


def test_quem_volta_nao_pega_a_tela_de_volta_sozinho(bruno_e_vitor):
    """Vitor caiu com "Só público" guardado, Bruno pegou o público: quando
    Vitor reconecta, perde a tela em vez de mexer junto com o Bruno."""
    bruno, vitor, _, d_vitor = bruno_e_vitor
    vitor.emit('set_display_mode', {'mode': 'public'})
    info = next(i for i in connections.socketio_clients_by_sid.values() if i['device'] == d_vitor)
    sid = next(s for s, i in connections.socketio_clients_by_sid.items() if i is info)
    del connections.socketio_clients_by_sid[sid]
    bruno.emit('set_display_mode', {'mode': 'public'})
    destinos.ajustar_ao_conectar(d_vitor, 'vitor')
    assert display_state.device_mode(d_vitor) == 'none'
    assert destinos.dono('public') == 'bruno'


def test_status_mostra_quem_cuida_de_cada_tela(bruno_e_vitor):
    bruno, vitor, _, _ = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    st = [m['args'][0] for m in bruno.get_received() if m['name'] == 'telao_status'][-1]
    assert st['donos'] == {'public': 'bruno', 'monitor': 'vitor'}
    assert st['palco_com'] == 'vitor' and st['eu'] == 'bruno'
