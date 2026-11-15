"""Registro de segurança: entradas, senhas erradas, bloqueios e comandos de
tela recusados por falta de login.

Fica num arquivo próprio (instance/seguranca.log, fora do git), porque o
registro do sistema no Pi fica só na memória (journald Storage=volatile,
para poupar o cartão SD) e some a cada reinício: não dava para responder
"alguém tentou entrar?" sobre mais do que alguns dias. São poucas linhas
por dia, então quase não gasta o cartão. Gira em 5 arquivos de 1 MB.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

import paths

_logger = None


def _arquivo():
    pasta = paths.INSTANCE_DIR or os.path.join(paths.APP_DIR, 'instance')
    return os.path.join(pasta, 'seguranca.log')


def _registro():
    global _logger
    if _logger is None:
        _logger = logging.getLogger('ucontrol.seguranca')
        _logger.setLevel(logging.INFO)
        if not os.environ.get('UCONTROL_TESTING'):
            try:
                os.makedirs(os.path.dirname(_arquivo()), exist_ok=True)
                h = RotatingFileHandler(_arquivo(), maxBytes=1_000_000, backupCount=5, encoding='utf-8')
                h.setFormatter(logging.Formatter('%(asctime)s %(message)s', '%Y-%m-%d %H:%M:%S'))
                _logger.addHandler(h)
            except OSError:
                logging.getLogger('ucontrol').warning('Registro de segurança: não deu para abrir %s', _arquivo())
    return _logger


def _limpo(texto, tam=120):
    return str(texto or '-').replace('\n', ' ').replace('\r', ' ')[:tam]


def registrar(evento, ip, **campos):
    """evento: login_ok, login_falhou, login_bloqueado, socket_recusado."""
    try:
        extra = ''.join(f' {k}={_limpo(v)!r}' for k, v in campos.items())
        _registro().info('%s ip=%s%s', evento, _limpo(ip, 60), extra)
    except Exception:
        logging.getLogger('ucontrol').debug('Registro de segurança falhou', exc_info=True)
