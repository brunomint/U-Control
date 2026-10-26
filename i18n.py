"""Tradução da interface. O texto em português do próprio código é a chave:
translations/<idioma>.json guarda "texto em português" -> "tradução", e o
que não estiver lá aparece em português (as telas vão sendo traduzidas aos
poucos). Só a interface: letras, Bíblias e nomes que a igreja cadastrou
ficam como estão.

Nas páginas: {{ _('Salvar música') }} ou {{ _('{n} músicas', n=3) }}.
No Python: from i18n import gettext as _. No JS: _t('Salvar música')
(static/js/i18n.js, com o dicionário servido por /i18n/<idioma>.js).

Idioma: o escolhido em Sistema → Idioma (tabela Setting); sem escolha, o
do navegador — quem instala com o navegador em inglês já abre em inglês,
e as igrejas que já usam continuam em português."""
import json
import os

from flask import g, has_request_context, request

import paths

PADRAO = 'pt'
# Nome de cada idioma escrito nele mesmo (é assim que a pessoa procura)
IDIOMAS = {'pt': 'Português', 'en': 'English'}
# lang="" do <html>
TAGS = {'pt': 'pt-BR', 'en': 'en'}

PASTA = os.path.join(paths.APP_DIR, 'translations')
_dicionarios = {}


def dicionario(idioma):
    """translations/<idioma>.json (o português não tem: é o próprio texto)."""
    if idioma == PADRAO or idioma not in IDIOMAS:
        return {}
    if idioma not in _dicionarios:
        with open(os.path.join(PASTA, f'{idioma}.json'), encoding='utf-8') as f:
            _dicionarios[idioma] = {k: v for k, v in json.load(f).items() if v}
    return _dicionarios[idioma]


def idioma_salvo():
    from models import Setting
    row = Setting.query.first()
    return row.language if row and row.language in IDIOMAS else None


def idioma_atual():
    """Lido uma vez por requisição; fora de uma (threads, scripts), português."""
    if not has_request_context():
        return PADRAO
    if 'uc_idioma' not in g:
        try:
            salvo = idioma_salvo()
        except Exception:  # banco ainda sem a coluna (antes do flask db upgrade)
            salvo = None
        g.uc_idioma = salvo or request.accept_languages.best_match(list(IDIOMAS), default=PADRAO)
    return g.uc_idioma


def gettext(texto, **valores):
    traduzido = dicionario(idioma_atual()).get(texto, texto)
    return traduzido.format(**valores) if valores else traduzido


def init_app(app):
    app.jinja_env.globals['_'] = gettext

    @app.context_processor
    def _idioma():
        idioma = idioma_atual()
        try:  # ?v= do dicionário no navegador: muda quando o arquivo muda
            versao = int(os.path.getmtime(os.path.join(PASTA, f'{idioma}.json')))
        except OSError:
            versao = 0
        return {'uc_lang': idioma, 'uc_lang_tag': TAGS[idioma], 'uc_i18n_v': versao}
