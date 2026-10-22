"""PowerPoint animado no telão: /apresentacao?svg=<url do _slide.svg>&slide=N
toca a versão SVG que o LibreOffice gera na conversão (gallery.py), com as
transições e animações, no tocador do próprio LibreOffice.

Cada tela roda o seu tocador; o servidor guarda onde a apresentação está
(slide e animação) e repassa os comandos do Controle:

- 'apresentacao_cmd' {cmd: 'next' | 'prev'} — do /presenter; vai pra todas
  as telas junto com a posição de partida ('de'), então uma tela que ficou
  pra trás alcança as outras antes de avançar;
- 'apresentacao_pos' — cada tela conta onde parou; o servidor guarda e
  repassa (o /presenter mostra "slide 3 de 7");
- outro slide da mesma apresentação escolhido na galeria não recarrega a
  página (seriam MB de SVG e sem transição): display.py chama ir_para().

Tela que abre ou recarrega no meio pergunta a posição em /api/apresentacao."""
import threading
from urllib.parse import parse_qs, urlsplit

from flask import Blueprint, jsonify, render_template
from flask_socketio import emit

from extensions import socketio

apresentacao_bp = Blueprint('apresentacao', __name__)

_estado = {'svg': None, 'slide': 0, 'step': 0, 'slides': None, 'steps': None}
_lock = threading.Lock()


def parse_url(url):
    """'/apresentacao?svg=...&slide=2' -> (svg, 2); outra URL -> (None, 0)."""
    partes = urlsplit(url or '')
    if partes.path != '/apresentacao':
        return None, 0
    q = parse_qs(partes.query)
    svg = (q.get('svg') or [None])[0]
    try:
        slide = max(0, int((q.get('slide') or ['0'])[0]))
    except ValueError:
        slide = 0
    return (svg if svg and svg.startswith('/static/imagens/') and svg.endswith('.svg') else None), slide


def comecar(url):
    """A apresentação vai ao ar (display.handle_show_image): começa no
    slide escolhido, sem animação nenhuma tocada."""
    svg, slide = parse_url(url)
    if svg:
        with _lock:
            _estado.update(svg=svg, slide=slide, step=0, slides=None, steps=None)


def ir_para(url):
    """Outro slide da apresentação que já está no ar: as telas pulam pra
    ele sem recarregar."""
    svg, slide = parse_url(url)
    with _lock:
        _estado.update(svg=svg, slide=slide, step=0, steps=None)
        estado = dict(_estado)
    socketio.emit('apresentacao_cmd', {'cmd': 'goto', 'svg': svg, 'slide': slide, 'step': 0})
    socketio.emit('apresentacao_pos', estado)


# Sem login, como /tela-do-pc: é uma tela
@apresentacao_bp.route('/apresentacao')
def apresentacao():
    return render_template('apresentacao.html')


@apresentacao_bp.route('/api/apresentacao')
def api_apresentacao():
    with _lock:
        return jsonify(dict(_estado))


@socketio.on('apresentacao_cmd')
def handle_apresentacao_cmd(data):
    cmd = (data or {}).get('cmd')
    if cmd not in ('next', 'prev'):
        return
    with _lock:
        if not _estado['svg']:
            return
        de = {'svg': _estado['svg'], 'slide': _estado['slide'], 'step': _estado['step']}
    emit('apresentacao_cmd', {'cmd': cmd, **de}, broadcast=True)


@socketio.on('apresentacao_pos')
def handle_apresentacao_pos(data):
    data = data or {}
    try:
        slide, step = int(data['slide']), int(data['step'])
        slides, steps = int(data['slides']), int(data['steps'])
    except (KeyError, TypeError, ValueError):
        return
    with _lock:
        if data.get('svg') != _estado['svg']:
            return  # tela atrasada, de outra apresentação
        novo = dict(_estado, slide=slide, step=step, slides=slides, steps=steps)
        if novo == _estado:
            return  # as outras telas já contaram
        _estado.update(novo)
    emit('apresentacao_pos', novo, broadcast=True)
