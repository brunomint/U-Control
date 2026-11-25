"""Slides do telão (página /slides, blueprints/slides.py): conjuntos com nome —
"Avisos", "Diretoria 2026", "Ministérios" —, cada um com o tema (fundo, letra
e transição de temas_store.py), e passando sozinho em loop ou na mão.

Tipos de slide (docs/PLANO-APRESENTACOES.md):
  {"tipo": "texto", "texto": "Culto de oração\\nquarta, 19h30"}
      (aceita a formatação dos avisos: **negrito**, {amarelo}…{/})
  {"tipo": "lista", "titulo": "Diretoria 2026", "por_tela": 6,
   "linhas": [["Presidente", "Fulano de Tal"], ["Tesoureiro", "Ciclano"]]}
      — se passar de por_tela linhas, vira várias telas ("2/3").

O que vai pro telão são as TELAS (telas()), já divididas; o telão só desenha
(static/js/slides_render.js). Os antigos Avisos em slides viraram o conjunto
"Avisos" (migração a1f5c8e2d940).
"""
from extensions import db
from models import ConjuntoSlides

MAX_CONJUNTOS = 100
MAX_SLIDES = 60
MAX_TEXTO = 500
MAX_LINHAS = 80
MAX_CAMPO = 120
POR_TELA_PADRAO = 6
POR_TELA = (2, 15)
SEGUNDOS_PADRAO = 10
SEGUNDOS = (3, 120)
NOME_AVISOS = 'Avisos'


def _inteiro(valor, minimo, maximo, padrao):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return padrao


def _campo(valor, maximo=MAX_CAMPO):
    return str(valor if valor is not None else '').strip()[:maximo]


def normalizar_slide(slide):
    """Slide válido, ou None (vazio/desconhecido: some ao salvar)."""
    if isinstance(slide, str):
        slide = {'tipo': 'texto', 'texto': slide}
    if not isinstance(slide, dict):
        return None
    if slide.get('tipo') == 'lista':
        linhas = []
        for linha in (slide.get('linhas') or [])[:MAX_LINHAS]:
            if isinstance(linha, dict):
                linha = [linha.get('rotulo'), linha.get('valor')]
            if not isinstance(linha, (list, tuple)):
                continue
            rotulo, valor = _campo(linha[0] if len(linha) > 0 else ''), _campo(linha[1] if len(linha) > 1 else '')
            if rotulo or valor:
                linhas.append([rotulo, valor])
        titulo = _campo(slide.get('titulo'))
        if not linhas and not titulo:
            return None
        return {'tipo': 'lista', 'titulo': titulo, 'linhas': linhas,
                'por_tela': _inteiro(slide.get('por_tela'), *POR_TELA, POR_TELA_PADRAO)}
    texto = str(slide.get('texto') or '').strip()[:MAX_TEXTO]
    return {'tipo': 'texto', 'texto': texto} if texto else None


def _tema_valido(tema_id):
    import temas_store
    return int(tema_id) if tema_id and temas_store.obter(tema_id) else None


def _para_dict(c):
    return {'id': c.id, 'nome': c.nome, 'tema_id': _tema_valido(c.tema_id),
            'segundos': c.segundos or SEGUNDOS_PADRAO, 'automatica': c.automatica is not False,
            'embaralhar': bool(c.embaralhar), 'slides': [s for s in map(normalizar_slide, c.slides or []) if s]}


def garantir_avisos():
    """Sem nenhum conjunto (instalação nova, testes): cria o "Avisos" vazio."""
    if ConjuntoSlides.query.first() is None:
        db.session.add(ConjuntoSlides(nome=NOME_AVISOS, segundos=SEGUNDOS_PADRAO, automatica=True,
                                      embaralhar=False, slides=[]))
        db.session.commit()


def listar():
    garantir_avisos()
    return [_para_dict(c) for c in ConjuntoSlides.query.order_by(ConjuntoSlides.nome).all()]


def obter(conjunto_id):
    try:
        c = db.session.get(ConjuntoSlides, int(conjunto_id))
    except (TypeError, ValueError):
        return None
    return _para_dict(c) if c else None


def salvar(dados, conjunto_id=None):
    """Cria (sem id) ou atualiza. ValueError('nome') sem nome; None se o id não existe."""
    dados = dados if isinstance(dados, dict) else {}
    nome = _campo(dados.get('nome'), 80)
    if not nome:
        raise ValueError('nome')
    if conjunto_id:
        c = db.session.get(ConjuntoSlides, int(conjunto_id))
        if c is None:
            return None
    else:
        if ConjuntoSlides.query.count() >= MAX_CONJUNTOS:
            raise ValueError('limite')
        c = ConjuntoSlides()
        db.session.add(c)
    c.nome = nome
    c.tema_id = _tema_valido(dados.get('tema_id'))
    c.segundos = _inteiro(dados.get('segundos'), *SEGUNDOS, SEGUNDOS_PADRAO)
    c.automatica = dados.get('automatica') is not False
    c.embaralhar = bool(dados.get('embaralhar'))
    c.slides = [s for s in map(normalizar_slide, (dados.get('slides') or [])[:MAX_SLIDES]) if s]
    db.session.commit()
    return _para_dict(c)


def apagar(conjunto_id):
    c = db.session.get(ConjuntoSlides, int(conjunto_id))
    if not c:
        return False
    db.session.delete(c)
    db.session.commit()
    return True


def telas(conjunto):
    """As telas que o telão mostra, na ordem: a lista longa já dividida."""
    saida = []
    for slide in conjunto.get('slides') or []:
        if slide['tipo'] != 'lista':
            saida.append(dict(slide))
            continue
        por_tela = slide.get('por_tela') or POR_TELA_PADRAO
        grupos = [slide['linhas'][i:i + por_tela] for i in range(0, len(slide['linhas']), por_tela)] or [[]]
        for n, grupo in enumerate(grupos, 1):
            tela = {'tipo': 'lista', 'titulo': slide['titulo'], 'linhas': grupo,
                    'parte': f'{n}/{len(grupos)}' if len(grupos) > 1 else ''}
            # Última tela mais curta: linhas invisíveis pra letra ficar do
            # mesmo tamanho das outras telas da lista (o telão aumenta até caber)
            if len(grupos) > 1 and len(grupo) < por_tela:
                tela['completar'] = por_tela - len(grupo)
            saida.append(tela)
    return saida


def texto_simples(tela):
    """A tela em texto puro (versão simples /lite, histórico do telão)."""
    if not isinstance(tela, dict):
        return str(tela or '')
    if tela.get('tipo') == 'lista':
        titulo = tela.get('titulo') or ''
        if tela.get('parte'):
            titulo = f"{titulo} ({tela['parte']})".strip()
        linhas = [': '.join(p for p in linha if p) for linha in tela.get('linhas') or []]
        return '\n'.join([titulo] + linhas if titulo else linhas)
    return tela.get('texto') or ''
