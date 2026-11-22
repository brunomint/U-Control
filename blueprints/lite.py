"""Versão simples ("lite") do U-Control, para tablet e iPad antigos que só
abrem pelo navegador (plano em docs/PLANO-LITE.md).

Cookie `uc_lite` do aparelho: '1' = versão simples (?lite=1), '0' = versão
completa sempre (?lite=0), sem cookie = automático: static/lite/detectar.js
testa o navegador em cada página normal e manda o antigo para cá.
Com '1', as páginas que o lite.css cobre usam o tema simples
(static/lite/lite.css, sem variáveis CSS, grid nem flexbox). O tema simples só
vale nas páginas que o lite.css cobre (PAGINAS_SIMPLES e as /lite/): as
outras continuam no tema normal, mesmo com o cookie. Sem o cookie, nada muda.

/lite/diag mostra o que o navegador do aparelho entende e, com um toque,
manda o resultado ao servidor (linha LITE_DIAG no log), para não ter que
copiar tudo à mão."""
import logging
import re

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import lite_estado

logger = logging.getLogger('ucontrol')

lite_bp = Blueprint('lite', __name__, url_prefix='/lite')

COOKIE = 'uc_lite'
_UM_ANO = 365 * 24 * 3600
_MAX_RELATORIO = 2000
# Páginas do app normal que o lite.css sabe desenhar
PAGINAS_SIMPLES = {'auth.login', 'auth.primeiro_acesso', 'utils.exibir_links'}


def ativo():
    """Este pedido usa o tema simples? ?lite=1/0 vale na hora, antes do cookie."""
    pedido = request.args.get('lite')
    if pedido in ('0', '1'):
        return pedido == '1'
    return request.cookies.get(COOKIE) == '1'


def nesta_pagina():
    """Tema simples nesta página: o aparelho pediu e a página tem versão simples."""
    return ativo() and (request.blueprint == 'lite' or request.endpoint in PAGINAS_SIMPLES)


@lite_bp.app_context_processor
def _no_template():
    return {'uc_lite': nesta_pagina()}


@lite_bp.after_app_request
def _guardar_escolha(response):
    pedido = request.args.get('lite')
    if pedido in ('0', '1'):
        response.set_cookie(COOKIE, pedido, max_age=_UM_ANO, samesite='Lax')
    return response


def depois_do_login(padrao):
    """Para onde o login manda: aparelho na versão simples vai para /lite/
    (o dashboard não funciona nele), a não ser que já fosse para uma página lite."""
    if not ativo() or padrao.startswith('/lite'):
        return padrao
    return url_for('lite.inicio')


# ---- Página inicial e telas (Fase 1) ----

_TELA_COOKIE = 'uc_lite_tela'
_ROTA_DA_TELA = {'monitor': 'lite.monitor', 'publico': 'lite.publico'}


def _so_caminho(destino):
    """Página de onde o aparelho veio (?de=), só se for daqui mesmo."""
    destino = destino or ''
    return destino if destino.startswith('/') and not destino.startswith('//') else ''


@lite_bp.route('/')
def inicio():
    escolhida = request.args.get('tela')
    if escolhida in _ROTA_DA_TELA:
        r = redirect(url_for(_ROTA_DA_TELA[escolhida]))
        r.set_cookie(_TELA_COOKIE, escolhida, max_age=_UM_ANO, samesite='Lax')
        return r
    de = _so_caminho(request.args.get('de'))
    lembrada = request.cookies.get(_TELA_COOKIE)
    # Abre direto na tela de sempre; "trocar tela" (?escolher=1) e o aviso
    # de página sem versão simples (?de=) param aqui
    if lembrada in _ROTA_DA_TELA and not de and not request.args.get('escolher'):
        return redirect(url_for(_ROTA_DA_TELA[lembrada]))
    return render_template('lite/inicio.html', de=de, logado=current_user.is_authenticated)


def _tela(tela):
    return render_template('lite/tela.html', tela=tela)


@lite_bp.route('/monitor')
def monitor():
    return _tela('monitor')


@lite_bp.route('/publico')
def publico():
    return _tela('publico')


@lite_bp.route('/api/estado')
def api_estado():
    """O que a tela mostra agora. ?rev= igual ao atual: só {"rev", "igual"}."""
    tela = request.args.get('tela')
    if tela not in lite_estado.TELAS:
        return jsonify({'erro': 'tela'}), 400
    e = lite_estado.estado(tela)
    if request.args.get('rev') == e['rev']:
        e = {'rev': e['rev'], 'igual': True}
    resposta = jsonify(e)
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta


@lite_bp.route('/diag')
def diag():
    return render_template('lite/diag.html')


@lite_bp.route('/diag/relatorio')
def diag_relatorio():
    """GET de propósito: navegador antigo manda com uma imagem, sem XHR nem
    CSRF. Só escreve uma linha no log (texto limpo e curto)."""
    texto = re.sub(r'[\x00-\x1f\x7f]+', ' ', request.args.get('d', ''))[:_MAX_RELATORIO]
    logger.warning('LITE_DIAG ip=%s %s', request.remote_addr, texto)
    return '', 204


# ---- Cifras dos músicos (Fase 1B) ----

@lite_bp.route('/cifras')
def cifras():
    """Ordem do culto com link para a cifra de cada música. Sem login, como o /view."""
    import lite_cifras
    chave, ordem, proximos = lite_cifras.escolher_ordem(request.args.get('order'))
    return render_template('lite/cifras.html', chave=chave, ordem=ordem,
                           itens=lite_cifras.itens_da_ordem(ordem), proximos=proximos)


@lite_bp.route('/cifra/<int:song_id>')
def cifra(song_id):
    import lite_cifras
    import orders_store
    from letra_formato import musica_sem_formato
    from songs_store import get_song, musica_na_ordem
    song = musica_na_ordem(musica_sem_formato(get_song(song_id)))
    if not song:
        return render_template('lite/cifras.html', chave=None, ordem={}, itens=[], proximos=[],
                               erro='Música não encontrada.'), 404
    tom = lite_cifras.normal(lite_cifras.numero(request.args.get('tom'), -11, 11))
    capo = lite_cifras.numero(request.args.get('capo'), 0, 11)
    chave = request.args.get('order') if orders_store.KEY_RE.match(request.args.get('order') or '') else None
    anterior, proxima = lite_cifras.vizinhas(orders_store.get_order(chave), song_id) if chave else (None, None)

    def link(**mudar):
        """Esta mesma cifra com outro tom/capo (ou outra música), mantendo o resto."""
        args = {'song_id': song_id, 'order': chave, 'tom': tom, 'capo': capo, **mudar}
        return url_for('lite.cifra', **{k: v for k, v in args.items() if v})

    return render_template('lite/cifra.html', song=song, chave=chave, tom=tom, capo=capo,
                           anterior=anterior, proxima=proxima, link=link,
                           **lite_cifras.montar_cifra(song, tom, capo))


# ---- Controle simples (Fase 3) ----

@lite_bp.route('/controle', methods=['GET', 'POST'])
@login_required
def controle():
    """Botões do telão por formulário (lite_controle.py). Depois de cada
    ação volta para a página (POST → redirect), com o resultado no alto."""
    import lite_cifras
    import lite_controle
    if request.method == 'POST':
        ok, mensagem, extra = lite_controle.acao(request.form.get('acao', ''), request.form.get('valor', ''))
        if mensagem:
            flash(mensagem, 'ok' if ok else 'erro')
        return redirect(url_for('lite.controle', **(extra or {})))
    chave, ordem, _ = lite_cifras.escolher_ordem(None)
    itens = []
    for item in lite_cifras.itens_da_ordem(ordem):
        if item['tipo'] == 'musica':
            item['url'] = f"/lyrics/{item['id']}?order={chave}"
        elif item['tipo'] == 'biblia':
            from blueprints.bible import generate_bible_url
            item['url'] = generate_bible_url(item['titulo'])
        itens.append(item)
    return render_template('lite/controle.html', e=lite_controle.estado(), modos=lite_controle.MODOS,
                           neutras=lite_controle.NEUTRAS, chave=chave, itens=itens,
                           assumir=request.args.get('assumir'))
