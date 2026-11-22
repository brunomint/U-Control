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

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

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
