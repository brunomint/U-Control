"""Proteções contra outros sites: de onde o tempo real aceita conexão e os
cabeçalhos que o navegador usa pra não deixar outro site embutir ou
confundir as páginas. O login dos eventos de socket fica em extensions.py
(OperatorSocketIO); o CSRF dos formulários, no Flask-WTF."""
from urllib.parse import urlsplit

from flask import request

# Telas que podem aparecer dentro de outro site: o site da igreja
# (repositório site-igreja, página "ao vivo") mostra /lyrics/display/public
# num iframe. São páginas sem login e sem ação, então embutir não é risco.
TELAS_EMBUTIVEIS = {
    'lyrics.lyrics_display', 'lyrics.lyrics_display_Public', 'lyrics.lyrics_display_obs',
    'bible.bible_display', 'display.monitor', 'display.serve_image', 'display.tela_do_pc',
    'countdown.countdown_page', 'utils.clock', 'apresentacao.apresentacao',
}


def mesmo_site(origin, environ):
    """cors_allowed_origins do Socket.IO: só a própria página conecta.
    Compara só o endereço (host:porta), não http/https — atrás do
    Cloudflare Tunnel o servidor recebe http e o navegador manda https.
    Sem Origin (cliente que não é navegador) passa: o login dos eventos
    continua valendo."""
    if not origin:
        return True
    host = urlsplit(origin).netloc
    return bool(host) and host in (environ.get('HTTP_HOST'), environ.get('HTTP_X_FORWARDED_HOST'))


def init_app(app):
    # Lax: o navegador não manda o login quando outro site faz um POST ou
    # abre o tempo real por baixo — só ao navegar pra cá de verdade.
    # (Atribuição, não setdefault: o Flask já traz SESSION_COOKIE_SAMESITE=None.)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

    @app.after_request
    def cabecalhos(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        if request.endpoint not in TELAS_EMBUTIVEIS:
            response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        return response
