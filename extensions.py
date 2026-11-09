"""Instâncias de extensão Flask, sem app vinculado ainda (padrão factory:
`.init_app(app)` acontece dentro de `create_app()`, em main.py). Módulo
independente — não importa de main.py nem de blueprints/, pra nunca criar
import circular conforme mais blueprints forem extraídos."""
import functools
import logging

from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

import registro_acoes

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# Eventos que as telas (projetor, monitor, OBS) mandam sem login: se
# identificar, avisar fim de vídeo e responder ao compartilhamento de tela.
PUBLIC_SOCKET_EVENTS = {
    'connect', 'disconnect', 'identify', 'video_ended',
    'screen_share_hello', 'screen_share_request', 'screen_share_answer', 'screen_share_ice',
    'apresentacao_pos',  # cada tela conta onde a apresentação está (ver blueprints/apresentacao.py)
}


def _screen_video_reset(message, args):
    """Ao carregar um vídeo, /monitor e /img (telas sem login) pedem
    "pausado no início" pra sincronizar o servidor — só essa forma passa."""
    data = args[0] if args and isinstance(args[0], dict) else {}
    if message == 'toggle_video_pause':
        return data.get('paused') is True
    if message == 'seek_video':
        return data.get('time') in (0, 0.0)
    return False


class OperatorSocketIO(SocketIO):
    """SocketIO em que todo evento exige operador logado, exceto os de
    PUBLIC_SOCKET_EVENTS. Antes qualquer pessoa que abrisse o site (ex.:
    um músico em /view) podia mandar show_image, set_ticker, blackout…
    pro telão sem login. O bloqueio fica aqui, e não em cada handler, pra
    que evento novo já nasça protegido."""

    def on(self, message, namespace=None):
        register = super().on(message, namespace)
        if message in PUBLIC_SOCKET_EVENTS:
            return register

        def decorator(handler):
            @functools.wraps(handler)
            def guarded(*args, **kwargs):
                reset_da_tela = _screen_video_reset(message, args)
                if not current_user.is_authenticated and not reset_da_tela:
                    logging.getLogger('ucontrol').warning(
                        'Socket: evento %r recusado (sem login)', message)
                    return None
                registro_acoes.registrar_evento(message, args)
                # Quem cuida de cada tela (destinos.py): ação numa tela de
                # outra pessoa, ou sem tela escolhida, não passa. Confere só
                # a ação que chegou: os handlers que ela chama por dentro
                # (ex.: passagem → cifra no palco) já foram autorizados.
                from flask import g
                if not reset_da_tela and not g.get('uc_autorizado'):
                    import destinos
                    motivo = destinos.autorizar(message, args)
                    if motivo:
                        registro_acoes.registrar_recusa(message, motivo)
                        from connections import sala_do_aparelho
                        self.emit('acao_recusada', {'motivo': motivo, 'evento': message},
                                  to=sala_do_aparelho())
                        return None
                    g.uc_autorizado = True
                    # A ação que chegou do navegador (os handlers chamados por
                    # dentro não são ela — ver evento_de_fora)
                    g.uc_evento_de_fora = handler
                    try:
                        return handler(*args, **kwargs)
                    finally:
                        # Nada disto vaza pra próxima ação (o mesmo contexto
                        # pode servir mais de um evento)
                        for chave in ('uc_autorizado', 'uc_modo_passagem', 'uc_evento_de_fora'):
                            g.pop(chave, None)
                if g.get('uc_evento_de_fora') is handler:
                    g.uc_evento_de_fora = None   # chamado de novo por dentro: já não é "de fora"
                return handler(*args, **kwargs)
            return register(guarded)
        return decorator


socketio = OperatorSocketIO()

csrf = CSRFProtect()


# gunicorn.conf.py roda workers=1/threads=16 — até 16 threads reais podem
# bater no SQLite ao mesmo tempo. Sem isso, um writer concorrente recebe
# "database is locked" na hora em vez de esperar. Sem efeito em bancos
# ':memory:' (usados nos testes) — SQLite ignora WAL nesse caso.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
