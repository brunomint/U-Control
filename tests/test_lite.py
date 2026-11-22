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
    assert 'precisa de um navegador mais novo' in html and '/control?lite=0' in html
    # ?de= só aceita caminho daqui
    assert 'evil' not in client.get('/lite/?de=//evil.com').get_data(as_text=True)
    client.get('/lite/?tela=publico')


@pytest.mark.parametrize('tela', ['monitor', 'publico'])
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
    yield
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
    assert _estado(client, 'publico', rev=a['rev']) == {'rev': a['rev'], 'igual': True}
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
    assert _estado(client, 'monitor') == {**_estado(client, 'monitor'), 'modo': 'imagem', 'url': '/static/uploads/foto.jpg'}
    # Parte mandada só ao monitor ("Só monitor")
    telao.set_monitor('cifra', '/lyrics/display?host=monitor')
    display_state._last_lyrics_payload_monitor = {**display_state._last_lyrics_payload, 'text': 'C\nsó do palco'}
    assert 'só do palco' in _estado(client, 'monitor')['html']
    assert _estado(client, 'publico')['linhas'] == ['letra do público']


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
