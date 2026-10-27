"""Atalhos: comandos do telão por um endereço web, pra botões físicos
(Stream Deck pelo Bitfocus Companion, módulo "Generic HTTP"), o QuickDeck
ou qualquer coisa que chame uma URL.

    GET|POST /api/atalho/<comando>?chave=<chave>      (ou cabeçalho X-UControl-Chave)

A chave fica em <instance>/atalhos_chave (página Sistema → Atalhos mostra e
troca). Sem login: quem tem a chave comanda o telão, como o Controle.

O que o servidor sabe fazer sozinho ele faz (tela preta, esconder texto,
liberar, avisos, cronômetro, relógio, avançar a apresentação animada).
"Próximo"/"anterior" na letra e na Bíblia depende de onde o operador está
— quem sabe qual é a próxima estrofe é a página aberta —, então vai pro
Controle usado por último, que faz o mesmo que a seta do teclado (pedal).

Os comandos reaproveitam os mesmos handlers de socket do Controle
(chamados por __wrapped__, sem a trava de login do OperatorSocketIO, e com
um "remetente" de mentira pra o emit() funcionar fora do socket)."""
import contextlib
import hmac
import os
import secrets
import threading
import time

from flask import Blueprint, current_app, jsonify, render_template, request, url_for
from flask_login import login_required

import display_state
from extensions import csrf, socketio
from i18n import gettext as tr

atalhos_bp = Blueprint('atalhos', __name__)

_REMETENTE = 'atalho-http'  # sid que não existe: resposta "só pra quem mandou" não vai pra ninguém
_controles = {}  # sid -> última vez que alguém mexeu naquele Controle
_lock = threading.Lock()


# --- chave ---------------------------------------------------------------

def _arquivo_chave():
    return os.path.join(current_app.instance_path, 'atalhos_chave')


def chave():
    caminho = _arquivo_chave()
    if os.path.exists(caminho):
        with open(caminho, encoding='utf-8') as f:
            valor = f.read().strip()
        if valor:
            return valor
    return trocar_chave()


def trocar_chave():
    valor = secrets.token_urlsafe(18)
    os.makedirs(os.path.dirname(_arquivo_chave()), exist_ok=True)
    with open(_arquivo_chave(), 'w', encoding='utf-8') as f:
        f.write(valor)
    return valor


def _autorizado():
    enviada = request.args.get('chave') or request.headers.get('X-UControl-Chave') or ''
    if not enviada and request.headers.get('Authorization', '').startswith('Bearer '):
        enviada = request.headers['Authorization'][7:]
    return bool(enviada) and hmac.compare_digest(enviada.strip(), chave())


@contextlib.contextmanager
def _como_socket():
    """Deixa o emit() dos handlers funcionar dentro de uma requisição HTTP."""
    request.namespace = '/'
    request.sid = _REMETENTE
    yield


def _handler(funcao):
    return getattr(funcao, '__wrapped__', funcao)


# --- Controle que recebe "próximo/anterior" -------------------------------

@socketio.on('atalho_ativo')
def handle_atalho_ativo(_data=None):
    """O Controle avisa que está aberto e foi usado (control.js)."""
    with _lock:
        _controles[request.sid] = time.time()


def esquecer(sid):
    """Chamado por connections.handle_disconnect."""
    with _lock:
        _controles.pop(sid, None)


def _navegar(direcao):
    import navegador_telao
    from blueprints import apresentacao
    if navegador_telao.aberto():  # site no telão por cima de tudo
        return _site('pagina-baixo' if direcao > 0 else 'pagina-cima')
    if apresentacao.no_ar():
        _handler(apresentacao.handle_apresentacao_cmd)({'cmd': 'next' if direcao > 0 else 'prev'})
        return {'ok': True, 'em': 'apresentação'}
    with _lock:
        sids = sorted(_controles, key=_controles.get, reverse=True)
    for sid in sids:
        try:
            resposta = socketio.call('atalho_navegar', {'direcao': direcao}, to=sid, timeout=3)
        except Exception:  # Controle fechado sem avisar / não respondeu
            esquecer(sid)
            continue
        if resposta and resposta.get('ok'):
            return {'ok': True, 'em': resposta.get('em')}
        return {'ok': False, 'erro': (resposta or {}).get('erro') or tr('O Controle não tem música, Bíblia ou fotos abertas no painel.')}
    return {'ok': False, 'erro': tr('Nenhum Controle aberto. Abra o Controle (com a música ou a Bíblia no painel).')}


# --- comandos --------------------------------------------------------------

def _liberar():
    from blueprints.display import handle_release_staged_content
    from extensions import db
    from models import StagedContent
    preparado = db.session.query(StagedContent).order_by(StagedContent.updated_at.desc()).first()
    if not preparado:
        return {'ok': False, 'erro': tr('Nada preparado pra liberar.')}
    _handler(handle_release_staged_content)({'kind': preparado.kind})
    return {'ok': True, 'liberado': preparado.label or preparado.kind}


def _tela_preta(modo, tipo='preta'):
    from blueprints.display import handle_blackout
    # Alternar: desliga se ESTA tela (preta/branca/logo) está no ar; se for
    # outra, troca pra esta
    no_ar = display_state._blackout_active and display_state._blackout_tipo == tipo
    ativo = (not no_ar) if modo == 'alternar' else modo == 'ligar'
    _handler(handle_blackout)({'active': ativo, 'tipo': tipo})
    return {'ok': True, 'tela_preta': ativo, 'tipo': display_state._blackout_tipo}


def _texto(modo):
    from blueprints.lyrics import handle_toggle_lyrics_visibility
    from models import LyricsState
    estado = LyricsState.query.first()
    visivel = estado.visible is not False if estado else True
    novo = (not visivel) if modo == 'alternar' else modo == 'mostrar'
    _handler(handle_toggle_lyrics_visibility)({'visible': novo})
    return {'ok': True, 'texto_visivel': novo}


def _aviso():
    from blueprints.ticker import TELAS, handle_set_ticker
    texto = (request.values.get('texto') or '').strip()
    if not texto:
        return {'ok': False, 'erro': tr('Falta o texto do aviso (?texto=...).')}
    telas = [t for t in (request.values.get('telas') or 'public').split(',') if t in TELAS] or ['public']
    _handler(handle_set_ticker)({'text': texto, 'targets': telas})
    return {'ok': True, 'aviso': texto, 'telas': telas}


def _aviso_tirar():
    from blueprints.ticker import TELAS, handle_stop_ticker
    telas = [t for t in (request.values.get('telas') or ','.join(TELAS)).split(',') if t in TELAS]
    _handler(handle_stop_ticker)({'targets': telas})
    return {'ok': True}


def _cronometro():
    from blueprints.countdown import handle_start_countdown
    from blueprints.display import handle_show_image
    try:
        segundos = int(float(request.values.get('minutos', 5)) * 60) + int(request.values.get('segundos', 0))
    except ValueError:
        return {'ok': False, 'erro': tr('Minutos inválidos.')}
    if segundos <= 0:
        return {'ok': False, 'erro': tr('Tempo tem que ser maior que zero.')}
    _handler(handle_start_countdown)({'duration_seconds': segundos, 'label': request.values.get('titulo', '')})
    _handler(handle_show_image)({'image_url': '/countdown'})
    return {'ok': True, 'segundos': segundos}


def _socket(nome_modulo, nome_funcao, dados=None):
    def fazer():
        import importlib
        funcao = getattr(importlib.import_module(nome_modulo), nome_funcao)
        _handler(funcao)(dados or {})
        return {'ok': True}
    return fazer


def _site(acao):
    import navegador_telao
    try:
        if acao == 'fechar':
            navegador_telao.fechar()
            estado = navegador_telao.estado()
        else:
            estado = navegador_telao.comando(acao)
    except navegador_telao.SiteErro as e:
        return {'ok': False, 'erro': str(e)}
    socketio.emit('site_estado', estado)
    return {'ok': True, 'em': 'site'}


def _relogio():
    from blueprints.display import handle_show_image
    _handler(handle_show_image)({'image_url': '/clock'})
    return {'ok': True}


# nome -> (descrição na página, função); a descrição é traduzida ao mostrar
# (atalhos_page), o nome do comando fica (é o endereço)
COMANDOS = {
    'proximo': ('Próximo: estrofe ou versículo aberto no painel do Controle, animação do PowerPoint ou página do site no ar', lambda: _navegar(1)),
    'anterior': ('Anterior', lambda: _navegar(-1)),
    'liberar': ('Liberar o que está preparado', _liberar),
    'tela-preta': ('Tela preta liga/desliga', lambda: _tela_preta('alternar')),
    'tela-preta-ligar': ('Tela preta: ligar', lambda: _tela_preta('ligar')),
    'tela-preta-desligar': ('Tela preta: desligar', lambda: _tela_preta('desligar')),
    'tela-branca': ('Tela branca liga/desliga', lambda: _tela_preta('alternar', 'branca')),
    'tela-logo': ('Tela com o logo da igreja liga/desliga', lambda: _tela_preta('alternar', 'logo')),
    'texto': ('Esconder/mostrar a letra ou o versículo', lambda: _texto('alternar')),
    'aviso': ('Mostrar aviso (?texto=...&telas=public,monitor,obs)', _aviso),
    'aviso-tirar': ('Tirar o aviso (?telas=... ou todas)', _aviso_tirar),
    'cronometro': ('Cronômetro no telão (?minutos=5)', _cronometro),
    'cronometro-pausar': ('Pausar o cronômetro', _socket('blueprints.countdown', 'handle_pause_countdown')),
    'cronometro-continuar': ('Continuar o cronômetro', _socket('blueprints.countdown', 'handle_resume_countdown')),
    'cronometro-zerar': ('Zerar o cronômetro', _socket('blueprints.countdown', 'handle_reset_countdown')),
    'relogio': ('Relógio no telão', _relogio),
    'site-baixo': ('Site no telão: descer uma página (Page Down)', lambda: _site('pagina-baixo')),
    'site-cima': ('Site no telão: subir uma página (Page Up)', lambda: _site('pagina-cima')),
    'site-fechar': ('Site no telão: fechar', lambda: _site('fechar')),
}


@atalhos_bp.route('/api/atalho/<comando>', methods=['GET', 'POST'])
@csrf.exempt
def api_atalho(comando):
    if not _autorizado():
        return jsonify({'ok': False, 'erro': tr('Chave inválida. Veja em Sistema → Atalhos.')}), 401
    if comando not in COMANDOS:
        return jsonify({'ok': False, 'erro': tr('Comando desconhecido: {comando}', comando=comando), 'comandos': sorted(COMANDOS)}), 404
    with _como_socket():
        resultado = COMANDOS[comando][1]()
    return jsonify(resultado), (200 if resultado.get('ok') else 409)


@atalhos_bp.route('/atalhos')
@login_required
def atalhos_page():
    from network_utils import PORTA, obter_endereco_ip
    base = f'http://{obter_endereco_ip()}:{PORTA}'
    comandos = [(nome, tr(desc), base + url_for('atalhos.api_atalho', comando=nome)) for nome, (desc, _) in COMANDOS.items()]
    return render_template('atalhos.html', chave=chave(), comandos=comandos, base=base)


@atalhos_bp.route('/api/atalhos/trocar-chave', methods=['POST'])
@login_required
def api_trocar_chave():
    return jsonify({'chave': trocar_chave()})
