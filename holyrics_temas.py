"""Importar temas do Holyrics pela API local dele (Arquivo > Configurações >
API Server, ação GetThemes, v2.27+). O arquivo de temas do Holyrics
(themes.hly) é fechado; a API devolve o objeto Theme documentado em
https://github.com/holyrics/API-Server (README, seção "Theme").

converter() traduz um Theme do Holyrics para um tema do U-Control
(temas_store.py). O que não tem equivalente fica de fora e vira aviso:
fundo de imagem/vídeo (a API não entrega o arquivo), brilho, espaço entre
letras, comentários."""
import re
from urllib.parse import urlsplit

import requests

import temas_store

TIMEOUT = 8


class ErroHolyrics(Exception):
    pass


def _cor(valor, padrao='#000000'):
    """'F5F5F5', 'F5F5F580' (RGBA) ou '#F5F5F5' -> '#f5f5f5'."""
    texto = str(valor or '').lstrip('#')
    return f'#{texto[:6].lower()}' if re.fullmatch(r'[0-9a-fA-F]{6}([0-9a-fA-F]{2})?', texto) else padrao


def _alfa(valor):
    """Transparência (0-100) do 'RRGGBBAA'; sem alfa, 100."""
    texto = str(valor or '').lstrip('#')
    return round(int(texto[6:8], 16) / 255 * 100) if re.fullmatch(r'[0-9a-fA-F]{8}', texto) else 100


def _misturar(cor, base, opacidade):
    """Cor do fundo com opacidade sobre a cor base (como o Holyrics desenha)."""
    a = max(0, min(100, float(opacidade if opacidade is not None else 100))) / 100
    c1, c2 = int(cor[1:], 16), int(base[1:], 16)
    canais = [round(((c1 >> s) & 255) * a + ((c2 >> s) & 255) * (1 - a)) for s in (16, 8, 0)]
    return '#' + ''.join(f'{v:02x}' for v in canais)


def _fonte(nome):
    nome = str(nome or '').lower()
    for chave, palavras in (('merriweather', ('merriweather',)), ('georgia', ('georgia', 'times', 'serif', 'garamond', 'cambria')),
                            ('verdana', ('verdana', 'tahoma')), ('roboto', ('roboto',)), ('manrope', ('manrope', 'montserrat', 'poppins'))):
        if any(p in nome for p in palavras) and not (chave == 'georgia' and 'sans' in nome):
            return chave
    return 'arial'


def _numero(valor, padrao=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def converter(tema):
    """Theme do Holyrics -> ({'nome', 'fundo', 'texto', 'transicao'}, [avisos])."""
    avisos = []
    fonte = tema.get('font') or {}
    alinha = tema.get('align') or {}
    margem = alinha.get('margin') or {}
    efeito = tema.get('effect') or {}
    faixa = tema.get('shape_fill') or {}
    ajustes = tema.get('settings') or {}
    fundo_h = tema.get('background') or {}

    tipo = fundo_h.get('type')
    if tipo == 'color':
        cor = _cor(fundo_h.get('id'))
        fundo = {'type': 'color', 'color': _misturar(cor, _cor(tema.get('base_color'), '#000000'), fundo_h.get('opacity', 100))}
    elif tipo == 'transparent':
        fundo = {'type': 'color', 'color': '#000000'}
    else:
        fundo = {'type': 'color', 'color': '#000000'}
        avisos.append('fundo')   # imagem/vídeo: a API não manda o arquivo

    # Tamanho no Holyrics: % da altura do slide; aqui: % da largura (vw) numa tela 16:9
    tamanho = _numero(fonte.get('size'), 10) * 9 / 16
    texto = {
        'fonte': _fonte(fonte.get('name')),
        'negrito': bool(fonte.get('bold')),
        'italico': bool(fonte.get('italic')),
        'cor': _cor(fonte.get('color'), '#ffffff'),
        'maiusculas': bool(ajustes.get('uppercase')),
        'tamanho_max': round(tamanho * 2) / 2 if tamanho else temas_store.TEXTO_PADRAO['tamanho_max'],
        'entrelinhas': round(1 + _numero(fonte.get('line_spacing'), 0.3), 2),
        'alinhamento': {'left': 'esquerda', 'right': 'direita'}.get(alinha.get('horizontal'), 'centro'),
        'posicao': {'top': 'topo', 'bottom': 'base'}.get(alinha.get('vertical'), 'meio'),
        'margem': round((_numero(margem.get('left'), 3) + _numero(margem.get('right'), 3)) / 2),
        'contorno_cor': _cor(efeito.get('outline_color')),
        'contorno': round(_numero(efeito.get('outline_weight')) / 10),
        'sombra': bool(_numero(efeito.get('shadow_x_weight')) or _numero(efeito.get('shadow_y_weight'))),
        'sombra_cor': _cor(efeito.get('shadow_color')),
        'caixa': bool(faixa.get('enabled')),
        'caixa_cor': _cor(faixa.get('color')),
        'caixa_opacidade': _alfa(faixa.get('color')),
        'caixa_arredondada': round(_numero(faixa.get('corner')) / 10),
    }
    if _numero(efeito.get('brightness_weight')):
        avisos.append('brilho')
    dados = temas_store.normalizar({'fundo': fundo, 'texto': texto, 'transicao': temas_store.TRANSICAO_PADRAO})
    nome = str(tema.get('name') or '').strip()[:80] or 'Tema do Holyrics'
    return {'nome': nome, **dados}, avisos


def _base(endereco):
    endereco = (endereco or '').strip().rstrip('/')
    if not re.match(r'^https?://', endereco):
        endereco = 'http://' + endereco
    partes = urlsplit(endereco)
    if not partes.hostname:
        raise ErroHolyrics('endereco')
    return f'{partes.scheme}://{partes.netloc}'


def buscar(endereco, token):
    """Lista de Theme do Holyrics (GetThemes). Levanta ErroHolyrics com um código curto."""
    url = f'{_base(endereco)}/api/GetThemes'
    try:
        r = requests.post(url, params={'token': token or ''}, json={}, timeout=TIMEOUT)
    except requests.RequestException:
        raise ErroHolyrics('conexao')
    try:
        dados = r.json()
    except ValueError:
        raise ErroHolyrics('resposta')
    if r.status_code == 401 or 'token' in str(dados.get('error', '')).lower():
        raise ErroHolyrics('token')
    if dados.get('status') != 'ok' or not isinstance(dados.get('data'), list):
        raise ErroHolyrics('resposta')
    return [t for t in dados['data'] if isinstance(t, dict)]
