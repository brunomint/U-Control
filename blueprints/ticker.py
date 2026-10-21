"""Avisos em ticker (texto rolando na base da tela) — estado isolado (em
memória + tabela TickerConfig), sem nenhuma variável compartilhada com
outra área do app (confirmado na exploração antes do split). Depende só
do utilitário compartilhado display_log.

O texto salvo é lido do banco uma vez na inicialização (init_ticker_state,
chamado por create_app() dentro de app_context) — não pode ser lido no
import do módulo como antes, porque isso rodava antes de
db.init_app()/app_context existirem."""
from flask import Blueprint, jsonify
from flask_socketio import emit
from sqlalchemy.exc import OperationalError

from display_log import append_display_log
from extensions import db, socketio
from models import TickerConfig

ticker_bp = Blueprint('ticker', __name__)


def _load_ticker_config():
    row = TickerConfig.query.first()
    return {'text': row.text or ''} if row else {'text': ''}


def _save_ticker_config(text):
    row = TickerConfig.query.first()
    if not row:
        row = TickerConfig()
        db.session.add(row)
    row.text = text
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


# Último texto mandado (pré-preenche o campo do Controle; salvo no banco)
_ticker_text = ''
# Aviso de cada tela agora: 'public' (tela pública), 'monitor' (palco),
# 'obs' (transmissão). Cada uma tem o seu — mandar pra uma não mexe nas
# outras (antes "Público" apagava o do palco, e o OBS só via "Ambos").
TELAS = ('public', 'monitor', 'obs')
_por_tela = {}
# Compatibilidade (telao.py, barrinha "No ar"): telas com aviso / se há algum
_ticker_targets = set()
_ticker_active = False  # nunca ativo no boot; exige comando explícito


def _telas(data):
    """targets: ['public', 'obs'...]; o formato antigo target='all'|'public'|
    'monitor' continua valendo ('all' = todas)."""
    targets = (data or {}).get('targets')
    if targets is None:
        alvo = str((data or {}).get('target', 'all'))
        targets = [alvo] if alvo in TELAS else list(TELAS)
    return [t for t in TELAS if t in targets]


def _sincronizar():
    global _ticker_active
    _ticker_targets.clear()
    _ticker_targets.update(_por_tela)
    _ticker_active = bool(_por_tela)


def init_ticker_state():
    """Chamado uma vez por create_app(), dentro de app_context — carrega o
    texto salvo do banco pro estado em memória. Tolera tabela ainda
    inexistente (banco recém-criado, antes do primeiro `flask db upgrade`
    rodar de verdade — `flask --app main db upgrade` importa main.py, e
    isso já chama create_app() antes do upgrade em si acontecer)."""
    global _ticker_text
    try:
        _ticker_text = _load_ticker_config().get('text', '')
    except OperationalError:
        db.session.rollback()


@ticker_bp.route('/api/ticker')
def ticker_api():
    # by_target: tela que abre/recarrega mostra o aviso dela (antes pegava
    # o último de qualquer tela)
    return jsonify({'text': _ticker_text, 'active': _ticker_active,
                    'targets': sorted(_ticker_targets), 'by_target': dict(_por_tela)})


def _enviar(telas, texto):
    for t in telas:
        emit('ticker_update', {'text': texto}, to=t)
    # Prévia/painel do Controle: atualiza o que está em cada tela
    emit('ticker_preview_update', {'text': texto, 'by_target': dict(_por_tela)}, broadcast=True)
    import telao
    telao.broadcast_status()


@socketio.on('set_ticker')
def handle_set_ticker(data):
    global _ticker_text
    texto = str((data or {}).get('text', '')).strip()
    telas = _telas(data)
    for t in telas:
        if texto:
            _por_tela[t] = texto
        else:
            _por_tela.pop(t, None)
    _sincronizar()
    if texto:
        _ticker_text = texto
        _save_ticker_config(texto)
        append_display_log({'type': 'ticker', 'title': texto})
    _enviar(telas, texto)


@socketio.on('stop_ticker')
def handle_stop_ticker(data):
    telas = _telas(data)
    for t in telas:
        _por_tela.pop(t, None)
    _sincronizar()
    _enviar(telas, '')
