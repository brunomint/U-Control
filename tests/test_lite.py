"""Versão simples (blueprints/lite.py, docs/PLANO-LITE.md): diagnóstico,
tema simples por aparelho e as regras de CSS/JS para navegador antigo."""
import logging
import os
import re

import pytest

PASTA_LITE = os.path.join(os.path.dirname(__file__), '..', 'static', 'lite')


def _arquivos(ext):
    return sorted(os.path.join(PASTA_LITE, f) for f in os.listdir(PASTA_LITE) if f.endswith(ext))


def _sem_comentarios(texto):
    texto = re.sub(r'/\*.*?\*/', '', texto, flags=re.S)
    return re.sub(r'(^|[^:\\])//[^\n]*', r'\1', texto)


# ---- Fase 0: diagnóstico ----

def test_diag_abre_sem_login(client):
    r = client.get('/lite/diag')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'lite/diag.js' in html and 'lite/lite.css' in html
    assert 'app.css' not in html and 'socket.io' not in html


def test_relatorio_vai_para_o_log_limpo_e_curto(client, caplog):
    with caplog.at_level(logging.WARNING, logger='ucontrol'):
        r = client.get('/lite/diag/relatorio', query_string={'d': 'Android 6\nWebView 44' + 'x' * 5000})
    assert r.status_code == 204
    linhas = [m for m in caplog.messages if m.startswith('LITE_DIAG')]
    assert len(linhas) == 1
    assert '\n' not in linhas[0] and 'Android 6 WebView 44' in linhas[0]
    assert len(linhas[0]) < 2100


# ---- Fase 0B: tema simples ----

def test_login_normal_nao_muda(client):
    html = client.get('/login').get_data(as_text=True)
    assert 'css/app.css' in html and 'css/pages/login.css' in html
    assert 'lite/lite.css' not in html


def test_lite_1_troca_o_tema_e_guarda_no_aparelho(client):
    r = client.get('/login?lite=1')
    html = r.get_data(as_text=True)
    assert 'lite/lite.css' in html
    assert 'css/app.css' not in html and 'css/tokens.css' not in html and 'js/ui.js' not in html
    assert 'css/pages/login.css' not in html
    assert 'name="csrf_token"' in html          # o formulário continua funcionando
    assert any(c.startswith('uc_lite=1') for c in r.headers.getlist('Set-Cookie'))

    # Próxima página, sem ?lite: o cookie mantém o tema simples
    html = client.get('/login').get_data(as_text=True)
    assert 'lite/lite.css' in html

    r = client.get('/login?lite=0')
    assert 'css/app.css' in r.get_data(as_text=True)
    assert any(c.startswith('uc_lite=0') for c in r.headers.getlist('Set-Cookie'))
    assert 'lite/lite.css' not in client.get('/login').get_data(as_text=True)


def test_links_no_tema_simples_usa_a_barra_simples(logged_in_client):
    html = logged_in_client.get('/links?lite=1').get_data(as_text=True)
    assert 'lite-nav' in html
    assert '/static/css/nav.css' not in html and 'telao_bar.js' not in html
    assert 'copyUrl(' not in html
    normal = logged_in_client.get('/links?lite=0').get_data(as_text=True)
    assert '/static/css/nav.css' in normal and 'copyUrl(' in normal


def test_tema_simples_nao_vale_nas_outras_paginas(logged_in_client):
    """Aparelho marcado como simples: o dashboard (sem versão simples) fica normal."""
    logged_in_client.get('/login?lite=1')
    html = logged_in_client.get('/dashboard').get_data(as_text=True)
    assert 'css/app.css' in html and 'lite/lite.css' not in html
    assert '/static/css/nav.css' in html
    logged_in_client.get('/login?lite=0')


# ---- Fase 1: página inicial, telas e desvio automático ----

def test_inicio_mostra_as_duas_telas_e_lembra_a_escolha(client):
    html = client.get('/lite/').get_data(as_text=True)
    assert 'Monitor do palco' in html and 'Telão do público' in html
    assert 'socket.io' not in html and 'app.css' not in html

    r = client.get('/lite/?tela=monitor')
    assert r.status_code == 302 and r.headers['Location'].endswith('/lite/monitor')
    # Da próxima vez abre direto
    r = client.get('/lite/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/lite/monitor')
    # "trocar tela" e o aviso de página sem versão simples param na escolha
    assert client.get('/lite/?escolher=1').status_code == 200
    html = client.get('/lite/?de=/control').get_data(as_text=True)
    # "Abrir mesmo assim" vale só para aquela página: não grava "sempre a completa"
    assert 'precisa de um navegador mais novo' in html and '/control?completa=1' in html
    assert '/control?lite=0' not in html
    # ?de= só aceita caminho daqui
    assert 'evil' not in client.get('/lite/?de=//evil.com').get_data(as_text=True)
    client.get('/lite/?tela=publico')


@pytest.mark.parametrize('tela', ['monitor', 'publico', 'vocal', 'cronometro'])
def test_telas_abrem_sem_login_e_sem_js_novo(client, tela):
    r = client.get(f'/lite/{tela}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'lite/tela.js' in html and f'data-tela="{tela}"' in html
    assert 'socket.io' not in html and 'detectar.js' not in html


def test_paginas_normais_carregam_o_detector(client, logged_in_client):
    assert 'data-tema="1"' in client.get('/login').get_data(as_text=True)
    for pagina in ('/monitor', '/lyrics/display/public'):
        assert 'lite/detectar.js' in client.get(pagina).get_data(as_text=True), pagina
    assert 'lite/detectar.js' in logged_in_client.get('/dashboard').get_data(as_text=True)


def test_login_no_aparelho_simples_vai_para_o_inicio_lite(app):
    from tests.conftest import User  # noqa: F401  (usuário criado pelo logged_in_client)
    from werkzeug.security import generate_password_hash
    import main as ucontrol_main
    with app.app_context():
        if not User.query.filter_by(username='lite').first():
            ucontrol_main.db.session.add(User(username='lite', password=generate_password_hash('s', method='pbkdf2:sha256')))
            ucontrol_main.db.session.commit()
    c = app.test_client()
    c.get('/login?lite=1')
    r = c.post('/login', data={'username': 'lite', 'password': 's'})
    assert r.headers['Location'].endswith('/lite/')
    # Aparelho normal continua indo para o dashboard
    c2 = app.test_client()
    r = c2.post('/login', data={'username': 'lite', 'password': 's'})
    assert r.headers['Location'].endswith('/dashboard')


@pytest.fixture
def telao_limpo():
    import display_state
    import telao
    guardado = (telao._public, telao._monitor, display_state._last_lyrics_payload,
                display_state._last_lyrics_payload_monitor, dict(display_state._telas_neutras),
                display_state._current_display_mode)
    telao._public = {'kind': 'blank', 'url': ''}
    telao._monitor = None
    display_state._last_lyrics_payload = None
    display_state._last_lyrics_payload_monitor = None
    display_state._telas_neutras.update({'public': None, 'monitor': None})
    from blueprints import countdown, ticker
    ticker._por_tela.clear()
    contagem = dict(countdown._countdown_state)
    countdown._countdown_state['active'] = False
    yield
    ticker._por_tela.clear()
    countdown._countdown_state.clear()
    countdown._countdown_state.update(contagem)
    (telao._public, telao._monitor, display_state._last_lyrics_payload,
     display_state._last_lyrics_payload_monitor, neutras, display_state._current_display_mode) = guardado
    display_state._telas_neutras.update(neutras)


def _estado(client, tela, rev=None):
    r = client.get('/lite/api/estado', query_string={'tela': tela, **({'rev': rev} if rev else {})})
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    return r.get_json()


def _letra_no_ar(app, texto, titulo='Verso 1', proximo='Refrão'):
    import display_state
    import songs_store
    import telao
    with app.app_context():
        sid = songs_store.next_song_id()
        songs_store.save_song({'id': sid, 'title': 'Hino Lite', 'author': 'A',
                               'sections': [{'title': titulo, 'text': [texto]}]})
    display_state._last_lyrics_payload = {'title': titulo, 'type': 'text', 'text': texto,
                                          'songId': sid, 'sectionIndex': 0, 'nextTitle': proximo}
    display_state._current_display_mode = 'lyrics'
    telao.set_public('lyrics', '/lyrics/display/public')
    return sid


def test_estado_publico_e_monitor_com_letra(app, client, telao_limpo):
    assert client.get('/lite/api/estado?tela=outra').status_code == 400
    assert _estado(client, 'publico')['modo'] == 'vazio'

    _letra_no_ar(app, 'G       D\nGraça **sublime**\n// nota do palco\n____do Senhor')
    pub = _estado(client, 'publico')
    assert pub['modo'] == 'letra'
    assert pub['linhas'] == ['Graça sublime', 'do Senhor']   # sem cifra, nota, ** e ___
    assert pub['musica'] == 'Hino Lite' and pub['secao'] == 'Verso 1'

    # O monitor segue o público e mostra a cifra, com o que vem a seguir
    mon = _estado(client, 'monitor')
    assert mon['modo'] == 'cifra' and 'class="chord"' in mon['html']
    assert mon['a_seguir'] == 'Refrão'


def test_rev_so_muda_quando_o_conteudo_muda(app, client, telao_limpo):
    _letra_no_ar(app, 'primeira')
    a = _estado(client, 'publico')
    igual = _estado(client, 'publico', rev=a['rev'])
    assert igual['igual'] and igual['rev'] == a['rev'] and set(igual) == {'rev', 'igual', 'agora'}
    _letra_no_ar(app, 'segunda')
    b = _estado(client, 'publico', rev=a['rev'])
    assert b['rev'] != a['rev'] and b['linhas'] == ['segunda']


def test_tela_preta_vale_por_tela(app, client, telao_limpo):
    import display_state
    _letra_no_ar(app, 'letra')
    display_state._telas_neutras['monitor'] = 'preta'
    assert _estado(client, 'monitor') ['modo'] == 'neutra'
    assert _estado(client, 'publico')['modo'] == 'letra'
    display_state._telas_neutras['public'] = 'logo'
    pub = _estado(client, 'publico')
    assert pub['modo'] == 'neutra' and pub['tipo'] == 'logo' and pub['url'] == '/logo-igreja.png'


def test_monitor_com_conteudo_proprio(app, client, telao_limpo):
    import display_state
    import telao
    _letra_no_ar(app, 'letra do público')
    telao.set_monitor_url('/clock')
    assert _estado(client, 'monitor')['modo'] == 'relogio'
    assert _estado(client, 'publico')['modo'] == 'letra'
    telao.set_monitor_url('/static/uploads/foto.jpg')
    foto = _estado(client, 'monitor')
    assert foto['modo'] == 'imagem' and foto['url'] == '/static/uploads/foto.jpg'
    # Parte mandada só ao monitor ("Só monitor")
    telao.set_monitor('cifra', '/lyrics/display?host=monitor')
    display_state._last_lyrics_payload_monitor = {**display_state._last_lyrics_payload, 'text': 'C\nsó do palco'}
    assert 'só do palco' in _estado(client, 'monitor')['html']
    assert _estado(client, 'publico')['linhas'] == ['letra do público']


# ---- Fase 1B: cifras dos músicos ----

CIFRAS_DIFICEIS = [
    'Bm7                  A/C#\n____Junto ao poço estava eu\n G2\nQuando um homem judeu',
    'C/E  G/B  Am7  F7M(9)', 'Dm7(b5)  G7(#9)  C#m7  Bbsus4', 'Em Deus eu confio', '| G | G7M | C9 | D4 |',
    'G-D-Em  C', 'F#7(5-)  C-7', 'A E 2x', 'Ab  Eb/G  Fm7  Db7M', 'C° Cº C+ Caug Cdim Cø', 'D(add9)  A(4)  Bm(11)',
    'E  B/D#  C#m  A//chords', 'Amor//lyrics',
]


def test_transposicao_igual_ao_js():
    """chord_lines.py (cifra do servidor) e static/js/chord_lines.js (cifra
    no navegador) dão o mesmo resultado em todos os tons. Pergunta 5 do
    plano: antes o Python não mantinha o acorde na coluna da sílaba."""
    import json
    import shutil
    import subprocess
    import chord_lines
    node = shutil.which('node')
    if not node:
        pytest.skip('node não instalado')
    codigo = ("global.window = {}; require('./static/js/chord_lines.js'); const CL = window.ChordLines;"
              f"const t = {json.dumps(CIFRAS_DIFICEIS)};"
              "console.log(JSON.stringify(t.map(x => ({l: x.split('\\n').map(CL.isChordLine),"
              " s: [-6,-5,-4,-3,-2,-1,1,2,3,4,5,6].map(n => CL.transposeBlockContent(x, n))}))));")
    js = json.loads(subprocess.run([node, '-e', codigo], capture_output=True, text=True, check=True).stdout)
    for texto, j in zip(CIFRAS_DIFICEIS, js):
        assert [chord_lines.is_chord_line(l) for l in texto.split('\n')] == j['l'], texto
        assert [chord_lines.transpose_block_content(texto, n) for n in [-6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6]] == j['s'], texto


def _culto_com_musica(app, chave, texto='G       D\nGraça sublime'):
    import orders_store
    import songs_store
    with app.app_context():
        ids = []
        for titulo in ('Primeira', 'Segunda'):
            sid = songs_store.next_song_id()
            songs_store.save_song({'id': sid, 'title': titulo, 'author': 'Autor', 'info': {'key': 'G', 'tempo': '72'},
                                   'sections': [{'title': 'Verso', 'text': [texto]},
                                                {'title': 'Coro', 'text': ['[Bis]\nC  G\nAleluia']}]})
            ids.append(sid)
        orders_store.save_order(chave, {'tipo': 'Culto da noite', 'dirigente': 'Ana', 'itens': [
            {'title': 'Primeira | Autor', 'url': f'/lyrics/{ids[0]}'},
            {'isBible': True, 'reference': 'Sl 23'},
            {'title': 'Segunda', 'url': f'/lyrics/{ids[1]}'},
        ]})
    return ids


def test_lista_de_cifras_do_culto(app, client):
    ids = _culto_com_musica(app, '2031-03-02')
    html = client.get('/lite/cifras?order=2031-03-02').get_data(as_text=True)
    assert 'Culto da noite' in html and 'Dirigente: Ana' in html
    assert f'/lite/cifra/{ids[0]}?order=2031-03-02' in html and 'Leitura: Sl 23' in html
    assert '<script' not in html          # a lista funciona sem JS nenhum
    assert client.get('/lite/cifras?order=2031-03-09').status_code == 200   # sem culto: aviso, sem erro


def test_cifra_com_tom_capo_e_vizinhas(app, client):
    ids = _culto_com_musica(app, '2031-03-16')
    url = f'/lite/cifra/{ids[0]}?order=2031-03-16'
    html = client.get(url).get_data(as_text=True)
    assert 'Tom: G' in html and 'Tom original: G' in html
    assert '<span class="chord">G</span>' in html and 'Graça sublime' in html
    assert '<h2>Bis</h2>' in html                       # [Bis] no texto vira um bloco
    assert f'/lite/cifra/{ids[1]}?order=2031-03-16' in html   # próxima música da ordem
    # Tom: +2 → A; Capo 2 → as formas de G de novo
    html = client.get(url + '&tom=2').get_data(as_text=True)
    assert 'Tom: A' in html and '<span class="chord">A</span>' in html
    html = client.get(url + '&tom=2&capo=2').get_data(as_text=True)
    assert 'Tom: A' in html and 'formas de G' in html and '<span class="chord">G</span>' in html
    # Grade de tons: o link do Ré muda o tom para +5 (de G para D, o caminho mais curto é -5)
    assert 'tom=-5' in client.get(url).get_data(as_text=True)
    assert client.get('/lite/cifra/999999').status_code == 404
    assert client.get(url + '&tom=abc&capo=99').status_code == 200


def test_detector_leva_o_view_para_as_cifras():
    texto = open(os.path.join(PASTA_LITE, 'detectar.js'), encoding='utf-8').read()
    assert "'/lite/cifras'" in texto and "'/lite/cifra/'" in texto
    assert 'completa=1' in texto   # "Abrir mesmo assim" respeitado só naquela página


def test_estado_das_telas_grava_varias_vezes_ao_mesmo_tempo(tmp_path, caplog):
    """Visto no Pi (22/11/2026): três aparelhos caindo juntos gravavam no mesmo
    telas.json.tmp e um deles dava FileNotFoundError."""
    import json
    import threading
    import destinos
    import estado_telas
    antes = (estado_telas._caminho, estado_telas._ultimo)
    estado_telas._caminho = str(tmp_path / 'telas.json')
    try:
        def gravar(i):
            for n in range(30):
                destinos._ultimo_clicado['teste'] = {'i': i, 'n': n}
                estado_telas.salvar()
        fios = [threading.Thread(target=gravar, args=(i,)) for i in range(8)]
        with caplog.at_level('ERROR', logger='ucontrol'):
            for f in fios:
                f.start()
            for f in fios:
                f.join()
        assert not [m for m in caplog.messages if 'Falha ao salvar' in m]
        assert json.loads((tmp_path / 'telas.json').read_text())['ultimo_clicado']['teste']
        assert not list(tmp_path.glob('*.tmp'))
    finally:
        destinos._ultimo_clicado.pop('teste', None)
        estado_telas._caminho, estado_telas._ultimo = antes


# ---- Fase 3: controle simples ----

def _acao(c, acao, valor=''):
    r = c.post('/lite/controle', data={'acao': acao, 'valor': valor})
    assert r.status_code == 302
    return r


def _mensagens(c):
    return c.get('/lite/controle').get_data(as_text=True)


def test_controle_pede_login_e_funciona_sem_js(client, logged_in_client):
    r = client.get('/lite/controle')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    html = logged_in_client.get('/lite/controle').get_data(as_text=True)
    assert 'name="csrf_token"' in html and 'Próximo' in html and 'Tela preta' in html
    assert '<script' not in html and 'socket.io' not in html


def test_controle_tela_preta_e_letra(app, logged_in_client, telao_limpo):
    import display_state
    from models import LyricsState
    _acao(logged_in_client, 'modo', 'public')
    _acao(logged_in_client, 'preta')
    assert display_state._telas_neutras == {'public': 'preta', 'monitor': None}
    assert 'Voltar (tirar tela preta)' in _mensagens(logged_in_client)
    _acao(logged_in_client, 'preta')
    assert display_state._telas_neutras['public'] is None
    _acao(logged_in_client, 'texto', 'esconder')
    with app.app_context():
        assert LyricsState.query.first().visible is False
    assert 'Mostrar a letra' in _mensagens(logged_in_client)
    _acao(logged_in_client, 'texto', 'mostrar')
    with app.app_context():
        assert LyricsState.query.first().visible is True


def test_controle_respeita_quem_cuida_da_tela(logged_in_client, telao_limpo):
    import connections
    import destinos
    import display_state
    connections.socketio_clients_by_sid['sid-outro'] = {'device': 'pc-outro', 'usuario': 'vitor'}
    display_state._device_modes['pc-outro'] = 'public'
    destinos._donos['public'] = 'vitor'
    try:
        r = _acao(logged_in_client, 'modo', 'public')
        assert 'assumir=public' in r.headers['Location']
        html = logged_in_client.get(r.headers['Location']).get_data(as_text=True)
        assert 'O público está com vitor.' in html and 'Assumir e ficar com Público' in html
        # Tela preta sem a tela: recusada, com o motivo
        _acao(logged_in_client, 'preta')
        assert display_state._telas_neutras['public'] is None
        _acao(logged_in_client, 'assumir', 'public')
        # O PC do outro deixa de mexer no público; sem tempo real, este
        # aparelho não segura a tela (ela fica livre), mas mexe nela
        assert display_state._device_modes['pc-outro'] == 'none'
        _acao(logged_in_client, 'preta')
        assert display_state._telas_neutras['public'] == 'preta'
    finally:
        connections.socketio_clients_by_sid.pop('sid-outro', None)
        display_state._device_modes.pop('pc-outro', None)


def test_controle_sem_controle_aberto_avisa(logged_in_client):
    _acao(logged_in_client, 'proximo')
    assert 'Nenhum Controle aberto' in _mensagens(logged_in_client)
    _acao(logged_in_client, 'abrir', 'https://fora.com/x')
    assert 'Item inválido' in _mensagens(logged_in_client)


# ---- Recado, letra para os vocais e tempo do pregador ----

def test_vocal_mostra_so_a_letra_do_palco(app, client, telao_limpo):
    _letra_no_ar(app, 'G       D\nGraça sublime')
    vocal = _estado(client, 'vocal')
    assert vocal['modo'] == 'letra' and vocal['linhas'] == ['Graça sublime']
    assert _estado(client, 'monitor')['modo'] == 'cifra'


def test_letreiro_vai_so_para_a_tela_dele(app, client, telao_limpo):
    from blueprints import ticker
    _letra_no_ar(app, 'letra')
    antes = _estado(client, 'monitor')['rev']
    ticker._por_tela['monitor'] = 'Repete o refrão'
    mon = _estado(client, 'monitor')
    assert mon['letreiro'] == 'Repete o refrão' and mon['rev'] != antes
    assert _estado(client, 'vocal')['letreiro'] == 'Repete o refrão'
    assert 'letreiro' not in _estado(client, 'publico')
    assert 'letreiro' not in _estado(client, 'cronometro')


def test_tempo_do_pregador(app, client, telao_limpo):
    import time
    import telao
    from blueprints import countdown
    e = _estado(client, 'cronometro')
    assert e['modo'] == 'relogio' and abs(e['agora'] - time.time() * 1000) < 5000
    igual = _estado(client, 'cronometro', rev=e['rev'])
    assert igual['igual'] and 'agora' in igual      # a hora do servidor vem sempre
    fim = int(time.time() * 1000) + 300000
    countdown._countdown_state.update({'active': True, 'paused': False, 'end_timestamp': fim, 'label': 'Pregação'})
    e = _estado(client, 'cronometro')
    assert e['modo'] == 'cronometro' and e['fim'] == fim and e['titulo'] == 'Pregação'
    countdown._countdown_state.update({'paused': True, 'paused_remaining': 61000})
    assert _estado(client, 'cronometro')['restante'] == 61000
    # Cronômetro no telão: a tela do público também mostra
    telao.set_public_url('/countdown')
    assert _estado(client, 'publico')['modo'] == 'cronometro'


def test_controle_manda_e_tira_recado(logged_in_client, telao_limpo):
    from blueprints import ticker
    _acao(logged_in_client, 'modo', 'all')
    r = logged_in_client.post('/lite/controle', data={'acao': 'recado', 'valor': '  Último refrão ', 'para': 'monitor'})
    assert r.status_code == 302
    assert ticker._por_tela == {'monitor': 'Último refrão'}
    html = _mensagens(logged_in_client)
    assert 'Recado no ar: Último refrão' in html and 'Tirar recado' in html
    _acao(logged_in_client, 'recado-tirar')
    assert ticker._por_tela == {}
    logged_in_client.post('/lite/controle', data={'acao': 'recado', 'valor': '   ', 'para': 'monitor'})
    assert 'Escreva o recado' in _mensagens(logged_in_client)


def test_controle_cronometro(logged_in_client, telao_limpo):
    from blueprints import countdown
    _acao(logged_in_client, 'modo', 'all')
    _acao(logged_in_client, 'cronometro', '10')
    c = countdown._countdown_state
    assert c['active'] and not c['paused'] and c['duration_ms'] == 600000
    html = _mensagens(logged_in_client)
    assert 'Cronômetro de 10 min rodando.' in html and ('9:59' in html or '10:00' in html) and 'Pausar' in html
    _acao(logged_in_client, 'cronometro-pausar')
    assert c['paused'] and 'Continuar' in _mensagens(logged_in_client)
    _acao(logged_in_client, 'cronometro-continuar')
    assert not c['paused']
    _acao(logged_in_client, 'cronometro-zerar')
    assert not c['active']
    _acao(logged_in_client, 'cronometro', '999')
    assert 'Tempo inválido' in _mensagens(logged_in_client) and not c['active']


def test_links_tem_o_qr_da_versao_simples(client):
    html = client.get('/links?lite=0').get_data(as_text=True)
    assert 'Versão simples (aparelho antigo)' in html and ':8585/lite/' in html
    assert 'Tablet ou iPad antigo' in client.get('/help').get_data(as_text=True)


# ---- Sinais de repetição (/: :/) fora do telão do público ----

REPETICOES = ['/: Ele era um, um dos maiorais. :/', '/:', ':/', 'Sopra /: meio da linha', 'http://site.com/:x',
              '  /: Glória ao Rei :/ (2x)', 'Normal sem sinal', '/: :/']


def test_sem_repeticao_igual_ao_js():
    import json
    import shutil
    import subprocess
    from letra_formato import sem_repeticao
    texto = '\n'.join(REPETICOES)
    py = sem_repeticao(texto)
    assert py.split('\n') == ['Ele era um, um dos maiorais.', 'Sopra meio da linha', 'http://site.com/:x',
                               'Glória ao Rei (2x)', 'Normal sem sinal']
    node = shutil.which('node')
    if not node:
        pytest.skip('node não instalado')
    codigo = ("global.window = {}; require('./static/js/letra_formato.js');"
              f"console.log(JSON.stringify(window.UcFormato.semRepeticao({json.dumps(texto)})));")
    assert json.loads(subprocess.run([node, '-e', codigo], capture_output=True, text=True, check=True).stdout) == py


def test_telao_simples_sem_repeticao_e_vocal_com(app, client, telao_limpo):
    _letra_no_ar(app, 'G       D\n/: Graça sublime :/\n:/')
    assert _estado(client, 'publico')['linhas'] == ['Graça sublime']
    assert _estado(client, 'vocal')['linhas'] == ['/: Graça sublime :/', ':/']


def test_telas_do_publico_usam_sem_repeticao():
    raiz = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'pages')
    for pagina in ('display_public.js', 'display_obs.js'):
        assert 'UcFormato.semRepeticao(' in open(os.path.join(raiz, pagina), encoding='utf-8').read(), pagina


# ---- Regras da seção 4 do plano (sem rede: só lendo os arquivos) ----

CSS_PROIBIDO = {
    'var(': r'var\(',
    'display: grid/flex': r'display\s*:\s*(-webkit-|-ms-)?(inline-)?(grid|flex)\b',
    'grid-*': r'grid-(template|area|column|row|gap)',
    'flex-*': r'(^|[\s;{])flex(-[a-z]+)?\s*:',
    'gap:': r'(^|[\s;{-])gap\s*:',
    'clamp(': r'clamp\(',
    'inset:': r'(^|[\s;{])inset\s*:',
    ':is/:has/:where': r':(is|has|where)\(',
    'vh/vw': r'\d(vh|vw|vmin|vmax)\b',
}


@pytest.mark.parametrize('arquivo', _arquivos('.css'), ids=os.path.basename)
def test_css_lite_sem_recurso_novo(arquivo):
    texto = _sem_comentarios(open(arquivo, encoding='utf-8').read())
    achados = [nome for nome, padrao in CSS_PROIBIDO.items() if re.search(padrao, texto, re.M)]
    assert not achados, f'{os.path.basename(arquivo)} usa {achados}'


JS_PROIBIDO = {
    'const/let': r'\b(const|let)\s+[A-Za-z_$\[{]',
    'arrow': r'=>',
    'template string': r'`',
    'class': r'\bclass\s+[A-Z]',
    'async/await': r'\b(async\s+function|await\s)',
    'fetch': r'\bfetch\s*\(',
    'Promise': r'\bPromise\s*[.(]',
    'classList': r'\.classList\b',
    'Array.from': r'Array\.from',
    'Object.assign(': r'Object\.assign\(',
    'startsWith/includes': r'\.(startsWith|includes)\(',
    'spread': r'\.\.\.[A-Za-z_$\[]',
    '?. / ??': r'\?\.[A-Za-z_$]|\?\?',
}


def _sem_strings(texto):
    # Só para a busca: texto entre aspas ('…' "…") pode citar nomes proibidos
    return re.sub(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"", "''", texto)


@pytest.mark.parametrize('arquivo', _arquivos('.js'), ids=os.path.basename)
def test_js_lite_so_es5(arquivo):
    texto = _sem_strings(_sem_comentarios(open(arquivo, encoding='utf-8').read()))
    achados = [nome for nome, padrao in JS_PROIBIDO.items() if re.search(padrao, texto)]
    assert not achados, f'{os.path.basename(arquivo)} usa {achados}'
