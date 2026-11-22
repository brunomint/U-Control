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
    assert any(c.startswith('uc_lite=;') for c in r.headers.getlist('Set-Cookie'))
    assert 'lite/lite.css' not in client.get('/login').get_data(as_text=True)


def test_links_no_tema_simples_usa_a_barra_simples(logged_in_client):
    html = logged_in_client.get('/links?lite=1').get_data(as_text=True)
    assert 'lite-nav' in html
    assert '/static/css/nav.css' not in html and 'telao_bar.js' not in html
    assert 'copyUrl(' not in html
    normal = logged_in_client.get('/links?lite=0').get_data(as_text=True)
    assert '/static/css/nav.css' in normal and 'copyUrl(' in normal


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
