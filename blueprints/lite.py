"""Versão simples ("lite") do U-Control, para tablet e iPad antigos que só
abrem pelo navegador (plano em docs/PLANO-LITE.md).

O aparelho passa a usar o tema simples (static/lite/lite.css, sem variáveis
CSS, grid nem flexbox) abrindo qualquer página com ?lite=1; o cookie
`uc_lite` guarda a escolha. ?lite=0 volta ao tema normal. O tema simples só
vale nas páginas que o lite.css cobre (PAGINAS_SIMPLES e as /lite/): as
outras continuam no tema normal, mesmo com o cookie. Sem o cookie, nada muda.

/lite/diag mostra o que o navegador do aparelho entende e, com um toque,
manda o resultado ao servidor (linha LITE_DIAG no log), para não ter que
copiar tudo à mão."""
import logging
import re

from flask import Blueprint, render_template, request

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
    if pedido == '1':
        response.set_cookie(COOKIE, '1', max_age=_UM_ANO, samesite='Lax')
    elif pedido == '0' and COOKIE in request.cookies:
        response.delete_cookie(COOKIE)
    return response


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
