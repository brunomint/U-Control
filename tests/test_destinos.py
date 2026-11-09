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
    destinos._seguindo.update({'public': True, 'monitor': True})   # o padrão de verdade
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


def test_aparelho_novo_conduz_a_passagem_mas_nao_mexe_na_tela(bruno_e_vitor):
    """Sem tela escolhida: passa música/slides/Bíblia/vídeo (passagem), mas
    não põe relógio, URL ou tela preta (isso é de quem cuida da tela)."""
    bruno, vitor, d_bruno, _ = bruno_e_vitor
    assert display_state.device_mode(d_bruno) == 'none'
    _foto(bruno, 'nova')
    assert display_state._last_image_url == '/static/imagens/nova.jpg'
    bruno.emit('blackout', {'tipo': 'preta', 'active': True, 'usar_modo': True})
    assert display_state._telas_neutras == {'public': None, 'monitor': None}
    assert any('Escolha' in m for m in _recusas(bruno))


def test_quem_escolhe_uma_tela_livre_fica_com_ela(bruno_e_vitor):
    bruno, vitor, d_bruno, d_vitor = bruno_e_vitor
    assert bruno.emit('set_display_mode', {'mode': 'public'}, callback=True)['ok']
    assert vitor.emit('set_display_mode', {'mode': 'monitor'}, callback=True)['ok']
    assert destinos.donos() == {'public': 'bruno', 'monitor': 'vitor'}
    _foto(bruno, 'do-bruno')
    assert display_state._last_image_url == '/static/imagens/do-bruno.jpg'


def test_os_dois_nao_passa_por_cima_de_quem_cuida(bruno_e_vitor):
    """O caso de 08/11: Vitor em "Os dois" tomava o público do Bruno. Agora
    pedir uma tela ocupada é recusado; e com o público sem seguir a
    passagem, o que o Vitor passa não chega ao público."""
    bruno, vitor, d_bruno, d_vitor = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    r = vitor.emit('set_display_mode', {'mode': 'all'}, callback=True)
    assert r == {'ok': False, 'ocupadas': {'public': 'bruno'}}
    assert display_state.device_mode(d_vitor) == 'none'
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    _foto(bruno, 'do-bruno')
    assert bruno.emit('seguir_passagem', {'tela': 'public', 'ligado': False}, callback=True)['ok']
    _foto(vitor, 'do-vitor')
    assert display_state._last_image_url == '/static/imagens/do-bruno.jpg'


def test_so_o_dono_liga_o_seguir_da_tela(bruno_e_vitor):
    bruno, vitor, _, _ = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    r = vitor.emit('seguir_passagem', {'tela': 'public', 'ligado': False}, callback=True)
    assert r == {'ok': False, 'dono': 'bruno'}
    assert destinos._seguindo['public'] is True


def _palco(monitor):
    return [(m['name'], m['args'][0]) for m in monitor.get_received()
            if m['name'] in ('display_monitor_content', 'update_lyrics', 'display_monitor_video')]


def _secao(sock, i, song=1):
    sock.emit('stage_content', {'kind': 'lyrics', 'payload': {
        'songId': song, 'sectionIndex': i, 'title': f'S{i}', 'text': f't{i}', 'type': 'text'}})
    sock.emit('release_staged_content', {'kind': 'lyrics'})


def test_roteiro_palco_acompanha_e_deixa_de_acompanhar(app, bruno_e_vitor):
    """O roteiro combinado em 08/11: o acompanhamento é decisão de quem
    cuida do palco, não uma permissão do público sobre o palco."""
    from extensions import socketio
    bruno, vitor, _, _ = bruno_e_vitor
    monitor = socketio.test_client(app)
    monitor.emit('identify', {'role': 'monitor'})
    try:
        bruno.emit('set_display_mode', {'mode': 'public'})          # Bruno: público
        vitor.emit('set_display_mode', {'mode': 'monitor'})         # 1. Vitor: palco
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': True})  # 2. liga
        monitor.get_received()
        _secao(bruno, 0)                                            # 3. música nova
        no_palco = _palco(monitor)                                  # 4. palco recebe a seção
        assert any(n == 'update_lyrics' and d.get('sectionIndex') == 0 for n, d in no_palco)
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': False})  # 5. desliga
        monitor.get_received()
        _secao(bruno, 0, song=2)                                    # 6. outra música
        assert telao._public_entry()['kind'] == 'lyrics'
        assert not _palco(monitor)                                  # palco fica na anterior
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': True})   # 7. liga de novo
        assert any('song_id=2' in (d.get('url') or '') for _, d in _palco(monitor))  # pega a atual
        vitor.emit('show_monitor_content', {'url': '/clock'})       # 8. relógio só no palco
        assert destinos._seguindo['monitor'] is False               # desliga sozinho
        monitor.get_received()
        _secao(bruno, 1, song=2)                                    # 9. próxima seção
        assert not _palco(monitor)                                  # palco continua no relógio
    finally:
        monitor.disconnect()


def test_biblia_nao_vai_pro_palco_que_segue(app, bruno_e_vitor):
    from extensions import socketio
    bruno, vitor, _, _ = bruno_e_vitor
    monitor = socketio.test_client(app)
    monitor.emit('identify', {'role': 'monitor'})
    try:
        bruno.emit('set_display_mode', {'mode': 'public'})
        vitor.emit('set_display_mode', {'mode': 'monitor'})
        monitor.get_received()
        bruno.emit('stage_content', {'kind': 'bible', 'payload': {'reference': 'Salmos 23:1', 'text': 'O Senhor'}})
        bruno.emit('release_staged_content', {'kind': 'bible'})
        assert not [m for m in monitor.get_received()
                    if m['name'] in ('update_bible', 'display_monitor_content', 'display_image')]
    finally:
        monitor.disconnect()


def test_video_e_passagem(app, bruno_e_vitor):
    """Vídeo segue a regra da letra: qualquer um passa; vai pras telas que seguem."""
    from extensions import socketio
    bruno, vitor, _, _ = bruno_e_vitor
    monitor = socketio.test_client(app)
    monitor.emit('identify', {'role': 'monitor'})
    try:
        bruno.emit('set_display_mode', {'mode': 'public'})
        vitor.emit('set_display_mode', {'mode': 'monitor'})
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': False})   # palco independente
        monitor.get_received()
        vitor_sem_tela = bruno  # quem passa o vídeo pode ser qualquer um
        vitor_sem_tela.emit('show_video', {'video_url': '/static/imagens/Video/espera.mp4'})
        assert display_state._video_state['url'] == '/static/imagens/Video/espera.mp4'
        assert not [m for m in monitor.get_received() if m['name'] in ('display_video', 'display_monitor_video')]
        assert destinos._seguindo['public'] is True   # vídeo não desliga o seguir
    finally:
        monitor.disconnect()


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


def test_foto_de_quem_esta_sem_tela_nao_vai_pro_palco_que_nao_segue(app, bruno_e_vitor):
    """A foto da Ana (sem tela) ia pro palco: o show_image obedecia ao
    exclude_monitor do navegador, e não às telas que seguem a passagem."""
    from extensions import socketio
    bruno, vitor, _, _ = bruno_e_vitor
    ana = _operator_socket(app, 'ana')
    try:
        bruno.emit('set_display_mode', {'mode': 'public'})
        vitor.emit('set_display_mode', {'mode': 'monitor'})
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': False})
        vitor.emit('show_monitor_content', {'url': '/clock'})
        ana.emit('show_image', {'image_url': '/static/imagens/da-ana.jpg'})
        assert display_state._last_image_url == '/static/imagens/da-ana.jpg'
        assert telao._monitor and telao._monitor.get('url') == '/clock'
        vitor.emit('seguir_passagem', {'tela': 'monitor', 'ligado': True})
        assert telao._monitor and 'da-ana.jpg' in telao._monitor.get('url', '')
    finally:
        ana.disconnect()


def test_biblia_posta_no_palco_nao_e_atropelada_pela_musica(bruno_e_vitor):
    """Teste de 09/11: o Vitor pôs a Bíblia no palco e a música do Bruno
    tirou ela de lá — o palco continuava seguindo a passagem."""
    bruno, vitor, _, _ = bruno_e_vitor
    bruno.emit('set_display_mode', {'mode': 'public'})
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    vitor.emit('show_monitor_content', {'url': '/bible/display'})
    assert destinos._seguindo['monitor'] is False
    bruno.emit('update_lyrics', {'songId': 1, 'sectionIndex': 0})
    assert telao._monitor and telao._monitor.get('url', '').startswith('/bible/display')


def test_dono_pondo_a_letra_de_volta_a_tela_acompanha_quem_conduz(app, bruno_e_vitor):
    """Teste de 09/11: tela preta no público e Bíblia no palco; depois o
    Bruno tirou a tela preta e o Vitor pôs a letra de volta, mas o celular
    de quem conduzia ouvia "Nenhuma tela…" — faltava tocar num botão."""
    bruno, vitor, _, _ = bruno_e_vitor
    cel = _operator_socket(app, 'ana')
    try:
        bruno.emit('set_display_mode', {'mode': 'public'})
        vitor.emit('set_display_mode', {'mode': 'monitor'})
        cel.emit('update_lyrics', {'songId': 1, 'sectionIndex': 0})
        bruno.emit('blackout', {'tipo': 'logo', 'active': True, 'usar_modo': True})
        vitor.emit('show_monitor_content', {'url': '/bible/display'})
        assert destinos._seguindo == {'public': False, 'monitor': False}
        cel.get_received()
        cel.emit('update_lyrics', {'songId': 1, 'sectionIndex': 1})
        assert any('Nenhuma tela' in m for m in _recusas(cel))
        # O dono tira a tela preta / põe a letra: volta a acompanhar sem botão
        bruno.emit('blackout', {'tipo': 'logo', 'active': False, 'usar_modo': True})
        vitor.emit('show_monitor_content', {'url': '/lyrics/display'})
        assert destinos._seguindo == {'public': True, 'monitor': True}
        cel.get_received()
        cel.emit('update_lyrics', {'songId': 1, 'sectionIndex': 2})
        assert not _recusas(cel)
    finally:
        cel.disconnect()


def test_tela_preta_sobre_o_relogio_nao_volta_pra_letra(bruno_e_vitor):
    """Tirar a tela preta só religa quem estava acompanhando antes dela."""
    bruno, vitor, _, _ = bruno_e_vitor
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    vitor.emit('show_monitor_content', {'url': '/clock'})
    vitor.emit('blackout', {'tipo': 'preta', 'active': True, 'usar_modo': True})
    vitor.emit('blackout', {'tipo': 'preta', 'active': False, 'usar_modo': True})
    assert destinos._seguindo['monitor'] is False


def test_letra_no_palco_pega_a_parte_atual(app, bruno_e_vitor):
    bruno, vitor, _, _ = bruno_e_vitor
    vitor.emit('set_display_mode', {'mode': 'monitor'})
    vitor.emit('show_monitor_content', {'url': '/clock'})
    bruno.emit('update_lyrics', {'songId': 7, 'sectionIndex': 3})   # Bruno sem tela: só o público segue
    vitor.emit('show_monitor_content', {'url': '/lyrics/display'})
    assert destinos._seguindo['monitor'] is True
    assert telao._monitor and telao._monitor.get('url', '').startswith('/lyrics/display')
