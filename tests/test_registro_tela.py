"""Registro da tela: o que o público viu, troca por troca (registro_tela.py)."""
import time
from unittest import mock

import pytest

import display_state
import main as ucontrol_main
import registro_tela
import telao
from models import TelaEvento
from test_smoke import _operator_socket


def _eventos():
    return TelaEvento.query.order_by(TelaEvento.id).all()


@pytest.fixture(autouse=True)
def registro_limpo():
    with ucontrol_main.app.app_context():
        TelaEvento.query.delete()
        ucontrol_main.db.session.commit()
        registro_tela._conteudo = None
        registro_tela._oculto = False
        registro_tela._ultimo_gravado = None
        registro_tela._proxima_limpeza = 0
        neutras = dict(display_state._telas_neutras)
        display_state._telas_neutras['public'] = None
        yield
        display_state._telas_neutras.update(neutras)
        display_state._last_lyrics_payload = None
        display_state._last_bible_payload = None


def _letra(texto, titulo='Refrão', **extra):
    display_state._last_lyrics_payload = {'title': titulo, 'text': texto, **extra}
    telao.set_public('lyrics', '/lyrics/display/public')


def test_letra_guarda_o_texto_sem_cifra_nem_marcacao():
    _letra('G   D\n**Santo**, {amarelo}santo{/}\n||\nÉ o Senhor')
    evento = _eventos()[-1]
    assert evento.tipo == 'letra'
    assert 'Refrão' in evento.titulo
    assert evento.texto == 'Santo, santo\nÉ o Senhor'


def test_divisao_usa_so_a_parte_que_foi_ao_ar():
    _letra('Parte 1\n||\nParte 2', textoPublico='Parte 2')
    assert _eventos()[-1].texto == 'Parte 2'


def test_guarda_uma_copia_do_tema_da_letra():
    tema = {'fundo': {'type': 'color', 'color': '#123456'}, 'texto': {'fonte': 'Inter'}}
    _letra('Santo', tema=tema)
    resposta = registro_tela.eventos_entre(0, int(time.time() * 1000) + 1000)
    assert resposta[-1]['tema'] == tema
    tema['fundo']['color'] = '#ffffff'   # mudar o tema depois não muda o registro
    assert registro_tela.eventos_entre(0, int(time.time() * 1000) + 1000)[-1]['tema']['fundo']['color'] == '#123456'


def test_mesmo_texto_com_tema_novo_vira_troca():
    _letra('Santo', tema={'fundo': {'color': '#111111'}})
    _letra('Santo', tema={'fundo': {'color': '#222222'}})
    assert len(_eventos()) == 2


def test_biblia_guarda_o_tema_dela():
    with mock.patch('temas_store.tema_da_biblia', return_value={'fundo': {'color': '#333333'}}):
        display_state._last_bible_payload = {'reference': 'Salmos 23:1', 'text': 'O Senhor'}
        telao.set_public('bible', '/bible/display')
    assert registro_tela.eventos_entre(0, int(time.time() * 1000) + 1000)[-1]['tema'] == {'fundo': {'color': '#333333'}}


def test_foto_e_tela_preta_nao_levam_tema():
    _letra('Santo', tema={'fundo': {'color': '#111111'}})
    telao.set_public_url('/static/imagens/a.jpg')
    display_state._telas_neutras['public'] = 'preta'
    registro_tela.tela_neutra()
    assert [e['tema'] for e in registro_tela.eventos_entre(0, int(time.time() * 1000) + 1000)][1:] == [None, None]


def test_reenvio_do_mesmo_conteudo_nao_vira_troca():
    _letra('Santo')
    _letra('Santo')
    assert len(_eventos()) == 1
    _letra('Digno')
    assert len(_eventos()) == 2


def test_biblia_guarda_referencia_e_versiculos():
    display_state._last_bible_payload = {'reference': 'João 3:16', 'verses': [{'num': 16, 'text': 'Porque Deus'}]}
    telao.set_public('bible', '/bible/display')
    evento = _eventos()[-1]
    assert (evento.tipo, evento.titulo, evento.texto) == ('biblia', 'João 3:16', '16 Porque Deus')


def test_video_e_foto_guardam_o_nome():
    telao.set_public('video', '/static/videos/abertura.mp4')
    telao.set_public_url('/static/imagens/foto%201.jpg')
    video, foto = _eventos()
    assert (video.tipo, video.titulo) == ('video', 'abertura.mp4')
    assert (foto.tipo, foto.titulo) == ('foto', 'foto 1.jpg')


def test_tela_preta_e_volta_ao_conteudo():
    _letra('Santo')
    display_state._telas_neutras['public'] = 'preta'
    registro_tela.tela_neutra()
    display_state._telas_neutras['public'] = None
    registro_tela.tela_neutra()
    assert [e.tipo for e in _eventos()] == ['letra', 'neutra', 'letra']
    assert _eventos()[-1].texto == 'Santo'


def test_esconder_e_mostrar_texto():
    _letra('Santo')
    registro_tela.texto_visivel(False)
    registro_tela.texto_visivel(True)
    assert [e.tipo for e in _eventos()] == ['letra', 'oculto', 'letra']


def test_conteudo_novo_reaparece_depois_de_esconder():
    _letra('Santo')
    registro_tela.texto_visivel(False)
    _letra('Digno')
    assert [e.texto for e in _eventos()][-1] == 'Digno'
    assert _eventos()[-1].tipo == 'letra'


def test_esconder_nao_vale_para_foto():
    telao.set_public_url('/static/imagens/a.jpg')
    registro_tela.texto_visivel(False)
    assert [e.tipo for e in _eventos()] == ['foto']


def test_hora_e_a_da_troca_em_milissegundos():
    antes = int(time.time() * 1000)
    _letra('Santo')
    assert antes <= _eventos()[-1].ts_ms <= int(time.time() * 1000)


def test_apaga_o_que_passou_do_prazo():
    velho = int(time.time() * 1000) - (registro_tela.DIAS_GUARDADOS + 1) * 86400 * 1000
    ucontrol_main.db.session.add(TelaEvento(ts_ms=velho, tipo='letra'))
    ucontrol_main.db.session.commit()
    _letra('Santo')
    ucontrol_main.db.session.expire_all()
    assert [e.ts_ms for e in _eventos() if e.ts_ms == velho] == []


def test_falha_no_registro_nao_atrapalha_o_telao():
    with mock.patch('registro_tela._gravar', side_effect=RuntimeError('banco fora')):
        telao.set_public('video', '/static/videos/a.mp4')
    assert telao._public['kind'] == 'video'


def test_evento_real_de_socket_registra(logged_in_client):
    socket = _operator_socket(ucontrol_main.app)
    socket.emit('update_lyrics', {'title': 'Verso', 'text': 'Grande é o Senhor', 'id': 'x'})
    socket.emit('toggle_lyrics_visibility', {'visible': False})
    socket.emit('blackout', {'active': True, 'tipo': 'preta', 'telas': ['public']})
    socket.emit('blackout', {'active': False, 'telas': ['public']})
    socket.disconnect()
    ucontrol_main.db.session.expire_all()
    assert [e.tipo for e in _eventos()] == ['letra', 'oculto', 'neutra', 'oculto']


def test_api_filtra_pelo_dia_e_exige_login(client, logged_in_client):
    meio_dia = int(time.mktime((2026, 11, 2, 12, 0, 0, 0, 0, -1)) * 1000)
    ucontrol_main.db.session.add_all([
        TelaEvento(ts_ms=meio_dia, tipo='letra', titulo='Hoje', texto='a'),
        TelaEvento(ts_ms=meio_dia + 86400 * 1000, tipo='letra', titulo='Amanhã', texto='b'),
    ])
    ucontrol_main.db.session.commit()
    resposta = logged_in_client.get('/api/registro-tela?dia=2026-11-02')
    assert [e['titulo'] for e in resposta.get_json()['eventos']] == ['Hoje']
    assert logged_in_client.get('/api/registro-tela?dia=abc').status_code == 400
    assert logged_in_client.get('/registro-tela').status_code == 200
