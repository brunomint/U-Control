"""Registro de quem fez o quê no telão: usuário, aparelho e modo de cada ação
de operador. Uma linha "ACAO ..." no log do serviço (journalctl -u
ucontrol-gunicorn | grep ACAO) e em instance/ucontrol.log.

Só observa: não muda nenhum comportamento e, se falhar, a ação segue
normalmente. Nasceu de um culto com dois operadores em que deu pra ver o
que foi ao ar, mas não quem mandou nem em qual modo o aparelho estava.

Ações por socket passam por aqui em extensions.OperatorSocketIO; as por HTTP,
no after_request de main.py. Nunca grava corpo de pedido inteiro: de socket
só as chaves de CAMPOS, de HTTP só método, caminho e resposta (senhas e
letras de música ficam de fora)."""
import logging

from flask import request
from flask_login import current_user

logger = logging.getLogger('ucontrol')

# Repetem sozinhos ou são detalhe técnico, sem decisão de ninguém
EVENTOS_IGNORADOS = {'telao_ping', 'preload_image', 'atalho_ativo', 'screen_share_offer'}
# Estado salvo pelas páginas a cada mudança de seção (293 vezes em 2 h de culto)
ROTAS_IGNORADAS = {'/save_lyrics_state', '/save_display_state'}
METODOS_DE_ACAO = {'POST', 'PUT', 'PATCH', 'DELETE'}

CAMPOS = (
    'url', 'url1', 'url2', 'image_url', 'video_url', 'tipo', 'active', 'telas',
    'usar_modo', 'use_active_mode', 'exclude_monitor', 'monitor_only', 'kind',
    'songId', 'sectionIndex', 'reference', 'paused',
)
MAX_VALOR = 80


def _limpo(valor):
    """Uma linha só, curta: o valor vem do navegador e vai pro log."""
    return ' '.join(str(valor).split())[:MAX_VALOR]


def _quem():
    import display_state
    usuario = current_user.username if current_user.is_authenticated else '-'
    aparelho = request.cookies.get('uc_device') or ''
    return (f'usuario={_limpo(usuario)} aparelho={_limpo(aparelho[:6]) or "-"} '
            f'modo={display_state.device_mode()}')


def _campos(dados):
    if not isinstance(dados, dict):
        return ''
    # stage_content e release trazem o conteúdo dentro de 'payload'
    interno = dados.get('payload')
    origem = {**interno, **dados} if isinstance(interno, dict) else dados
    return ''.join(f' {c}={_limpo(origem[c])}' for c in CAMPOS if origem.get(c) not in (None, ''))


def registrar_evento(evento, args):
    if evento in EVENTOS_IGNORADOS:
        return
    try:
        logger.info('ACAO %s evento=%s%s', _quem(), evento, _campos(args[0] if args else None))
    except Exception:
        logger.debug('Registro de ação falhou', exc_info=True)


def registrar_http(response):
    if request.method not in METODOS_DE_ACAO or request.path in ROTAS_IGNORADAS:
        return
    try:
        logger.info('ACAO %s evento=%s %s status=%s', _quem(), request.method,
                    _limpo(request.path), response.status_code)
    except Exception:
        logger.debug('Registro de ação falhou', exc_info=True)
