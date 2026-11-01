"""Temas do telão do público (página /temas, blueprints/temas.py).

Um tema é um fundo (o mesmo formato de Song.theme: cor, degradê, imagem ou
vídeo, com "escurecer") mais o estilo da letra. Só o telão do público usa
(static/js/tema_render.js); o palco continua com o visual dele.

Qual tema vale numa música, do mais forte para o mais fraco:
  1. o da música (Song.theme): {"tema_id": N} usa um tema salvo; um fundo
     solto (formato antigo, só cor/imagem/vídeo) troca só o fundo;
  2. o do culto (Order.tema_telao);
  3. o tema padrão (Setting.tema_padrao_id);
  4. o visual de sempre: fundo preto, letra branca com contorno preto.
"""
import copy
import re

from extensions import db
from models import Setting, Tema

FONTES = {
    'arial': "Arial, 'Liberation Sans', Helvetica, sans-serif",
    'manrope': "Manrope, Arial, sans-serif",
    'roboto': "Roboto, Arial, sans-serif",
    'merriweather': "Merriweather, Georgia, serif",
    'georgia': "Georgia, 'DejaVu Serif', serif",
    'verdana': "Verdana, 'DejaVu Sans', sans-serif",
}

# O visual que o telão sempre teve (display_public.css)
TEXTO_PADRAO = {
    'fonte': 'arial',
    'negrito': True,
    'italico': False,
    'cor': '#ffffff',
    'maiusculas': False,
    'tamanho_max': 15,          # vw: a letra começa aqui e encolhe até caber
    'entrelinhas': 1.3,
    'alinhamento': 'centro',    # esquerda | centro | direita
    'posicao': 'meio',          # topo | meio | base
    'margem': 5,                # % da tela em cada lado
    'contorno_cor': '#000000',
    'contorno': 4,              # 0 a 10 (centésimos do tamanho da letra)
    'sombra': True,
    'sombra_cor': '#000000',
    'caixa': False,
    'caixa_cor': '#000000',
    'caixa_opacidade': 50,
    'caixa_arredondada': 4,     # 0 a 10
}

FUNDO_PADRAO = {'type': 'color', 'color': '#000000'}

# Troca de um slide da letra para o próximo (só no telão do público).
# "nenhuma" é o que o telão sempre fez: troca na hora.
TRANSICOES = ('nenhuma', 'fade', 'deslizar', 'zoom')
TRANSICAO_PADRAO = {'tipo': 'nenhuma', 'duracao': 500}   # duracao em ms (200 a 2000)

# Degradês prontos (botão Tema da música e editor de temas); o nome passa por _() na tela
GRADIENTES = [
    ('Noite estrelada', 'linear-gradient(160deg,#0f0c29,#302b63,#24243e)'),
    ('Oceano profundo', 'linear-gradient(160deg,#0f2027,#203a43,#2c5364)'),
    ('Aurora', 'linear-gradient(160deg,#1a1a2e,#16213e,#0f3460)'),
    ('Crepúsculo roxo', 'linear-gradient(160deg,#1e1b4b,#312e81,#4338ca)'),
    ('Vinho e âmbar', 'linear-gradient(160deg,#4c0519,#7f1d1d,#92400e)'),
    ('Floresta', 'linear-gradient(160deg,#052e16,#14532d,#166534)'),
    ('Bruma dourada', 'linear-gradient(160deg,#1c1917,#44403c,#78350f)'),
    ('Éter', 'linear-gradient(160deg,#0c4a6e,#075985,#0369a1)'),
    ('Café escuro', 'linear-gradient(160deg,#0d0500,#3b1a08,#6b3a1f)'),
    ('Mogno', 'linear-gradient(160deg,#1a0800,#5c2206,#8b4513)'),
    ('Âmbar profundo', 'linear-gradient(160deg,#1a0900,#4a1c00,#92400e)'),
    ('Terra queimada', 'linear-gradient(160deg,#0d0500,#431407,#7c2d12)'),
    ('Canela', 'linear-gradient(160deg,#1c0800,#6b3a1f,#a16207)'),
    ('Ouro velho', 'linear-gradient(160deg,#1c1004,#4a3000,#854d0e)'),
    ('Cobre e noite', 'linear-gradient(160deg,#0d0500,#292524,#7c3a00)'),
    ('Chocolate', 'linear-gradient(160deg,#030000,#1c0a00,#5c2a0a)'),
]

_COR = re.compile(r'^#[0-9a-fA-F]{6}$')
_ESCOLHAS = {'alinhamento': ('esquerda', 'centro', 'direita'), 'posicao': ('topo', 'meio', 'base')}
_NUMEROS = {
    'tamanho_max': (4, 20), 'entrelinhas': (0.9, 2.0), 'margem': (0, 25), 'contorno': (0, 10),
    'caixa_opacidade': (0, 100), 'caixa_arredondada': (0, 10),
}


def _numero(valor, minimo, maximo, padrao):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return padrao
    n = max(minimo, min(maximo, n))
    return int(n) if float(n).is_integer() and isinstance(padrao, int) else round(n, 2)


def normalizar_fundo(fundo):
    """Fundo válido (formato de Song.theme) ou None."""
    if not isinstance(fundo, dict):
        return None
    tipo = fundo.get('type')
    limpo = None
    if tipo == 'color' and _COR.match(str(fundo.get('color') or '')):
        limpo = {'type': 'color', 'color': fundo['color']}
    elif tipo == 'gradient' and isinstance(fundo.get('css'), str) and fundo['css'].startswith(('linear-gradient(', 'radial-gradient(')) \
            and not re.search(r'url\s*\(|[;{}<>]', fundo['css']):
        limpo = {'type': 'gradient', 'css': fundo['css'][:300]}
    elif tipo in ('image', 'video') and isinstance(fundo.get('url'), str) and fundo['url'].startswith('/static/'):
        limpo = {'type': tipo, 'url': fundo['url'][:500]}
    if limpo and tipo in ('image', 'video'):
        escurecer = _numero(fundo.get('escurecer'), 0, 80, 0)
        if escurecer:
            limpo['escurecer'] = escurecer
    return limpo


def normalizar_texto(texto):
    texto = texto if isinstance(texto, dict) else {}
    limpo = {}
    for chave, padrao in TEXTO_PADRAO.items():
        valor = texto.get(chave, padrao)
        if chave == 'fonte':
            limpo[chave] = valor if valor in FONTES else padrao
        elif chave in _ESCOLHAS:
            limpo[chave] = valor if valor in _ESCOLHAS[chave] else padrao
        elif chave in _NUMEROS:
            limpo[chave] = _numero(valor, *_NUMEROS[chave], padrao)
        elif isinstance(padrao, bool):
            limpo[chave] = bool(valor)
        else:  # cores
            limpo[chave] = valor if _COR.match(str(valor or '')) else padrao
    return limpo


def normalizar_transicao(transicao):
    transicao = transicao if isinstance(transicao, dict) else {}
    tipo = transicao.get('tipo')
    return {'tipo': tipo if tipo in TRANSICOES else TRANSICAO_PADRAO['tipo'],
            'duracao': int(_numero(transicao.get('duracao'), 200, 2000, TRANSICAO_PADRAO['duracao']))}


def normalizar(dados):
    dados = dados if isinstance(dados, dict) else {}
    return {'fundo': normalizar_fundo(dados.get('fundo')) or dict(FUNDO_PADRAO), 'texto': normalizar_texto(dados.get('texto')),
            'transicao': normalizar_transicao(dados.get('transicao'))}


def listar():
    return [{'id': t.id, 'nome': t.nome, **normalizar(t.dados)} for t in Tema.query.order_by(Tema.nome).all()]


def obter(tema_id):
    try:
        tema = db.session.get(Tema, int(tema_id))
    except (TypeError, ValueError):
        return None
    return {'id': tema.id, 'nome': tema.nome, **normalizar(tema.dados)} if tema else None


def salvar(nome, dados, tema_id=None):
    nome = (nome or '').strip()[:80]
    if not nome:
        raise ValueError('nome')
    tema = db.session.get(Tema, int(tema_id)) if tema_id else Tema()
    if tema is None:
        return None
    tema.nome = nome
    tema.dados = normalizar(dados)
    if not tema_id:
        db.session.add(tema)
    db.session.commit()
    return obter(tema.id)


def apagar(tema_id):
    tema = db.session.get(Tema, int(tema_id))
    if not tema:
        return False
    db.session.delete(tema)
    config = Setting.query.first()
    if config and config.tema_padrao_id == tema.id:
        config.tema_padrao_id = None
    from models_orders import Order
    Order.query.filter_by(tema_telao=tema.id).update({'tema_telao': None})
    db.session.commit()
    return True


def padrao_id():
    config = Setting.query.first()
    return config.tema_padrao_id if config else None


def definir_padrao(tema_id):
    config = Setting.query.first()
    if config is None:
        config = Setting()
        db.session.add(config)
    config.tema_padrao_id = int(tema_id) if tema_id and obter(tema_id) else None
    db.session.commit()
    return config.tema_padrao_id


def tema_do_culto(chave_culto):
    if not chave_culto:
        return None
    from models_orders import Order
    order = db.session.get(Order, str(chave_culto))
    return obter(order.tema_telao) if order and order.tema_telao else None


def resolver(tema_da_musica, chave_culto=None):
    """{'fundo', 'texto', 'nome'} que o telão do público mostra para a música."""
    da_musica = tema_da_musica if isinstance(tema_da_musica, dict) else None
    escolhido = obter(da_musica['tema_id']) if da_musica and da_musica.get('tema_id') else None
    base = escolhido or tema_do_culto(chave_culto) or (obter(padrao_id()) if padrao_id() else None)
    resultado = copy.deepcopy(base) if base else {'fundo': dict(FUNDO_PADRAO), 'texto': dict(TEXTO_PADRAO),
                                                  'transicao': dict(TRANSICAO_PADRAO), 'nome': None}
    fundo_solto = normalizar_fundo(da_musica) if da_musica and not da_musica.get('tema_id') else None
    if fundo_solto:
        resultado['fundo'] = fundo_solto
    return {'fundo': resultado['fundo'], 'texto': resultado['texto'], 'transicao': resultado['transicao'],
            'nome': resultado.get('nome')}
