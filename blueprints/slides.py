"""Slides do telão (/slides): conjuntos com nome ("Avisos", "Diretoria
2026"...) em slides de texto ou lista, com o visual de um tema. Antes do
culto, na oferta, nos intervalos. Os dados ficam em slides_store.py.

Um conjunto passa SOZINHO (em loop, no tempo escolhido — o rodízio roda no
próprio telão, display_public.js) ou NA MÃO (o servidor guarda a posição;
Anterior/Próximo pela página, pelo Controle — setas e pedal — e pelos
atalhos do Stream Deck, blueprints/atalhos.py).

No telão o modo continua se chamando 'avisos' (display_state, telao.py,
registro_tela.py, lite_estado.py) e os eventos também: 'avisos_exibir'
(a lista de telas, uma vez), 'avisos_parar' e 'slides_ir' {pos} (na mão).
Qualquer outra coisa no telão (letra, foto, vídeo, Bíblia) para os slides.
O palco não mostra slides."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

import display_state
import slides_store
import temas_store
from extensions import socketio
from i18n import gettext as tr

slides_bp = Blueprint('slides', __name__)


def payload(conjunto, pos=0):
    telas = slides_store.telas(conjunto)
    return {'conjunto_id': conjunto['id'], 'nome': conjunto['nome'], 'telas': telas,
            # 'slides' em texto: versão simples (/lite) e histórico do telão
            'slides': [slides_store.texto_simples(t) for t in telas],
            'segundos': conjunto['segundos'], 'automatica': conjunto['automatica'],
            'embaralhar': conjunto['embaralhar'] and conjunto['automatica'],
            'pos': max(0, min(pos, len(telas) - 1)) if telas else 0,
            'tema': temas_store.resolver({'tema_id': conjunto['tema_id']} if conjunto['tema_id'] else None)}


def no_ar():
    return display_state._current_display_mode == 'avisos' and bool(display_state._avisos_payload)


def no_ar_na_mao():
    return no_ar() and not display_state._avisos_payload.get('automatica')


def resumo_no_ar():
    """Pro Controle (telao.py): o que está passando e em que tela."""
    if not no_ar():
        return None
    p = display_state._avisos_payload
    return {'id': p.get('conjunto_id'), 'nome': p.get('nome') or '', 'pos': p.get('pos', 0),
            'total': len(p.get('telas') or p.get('slides') or []), 'automatica': bool(p.get('automatica'))}


def _no_telao(dados):
    import telao
    display_state._current_display_mode = 'avisos'
    display_state._avisos_payload = dados
    socketio.emit('avisos_exibir', dados)
    telao.set_public('avisos', '/lyrics/display/public')
    telao.broadcast_status()


def atualizar_no_ar(conjunto_id=None):
    """O conjunto no ar (ou o tema dele) mudou: manda de novo, na mesma tela."""
    if not no_ar():
        return
    atual = display_state._avisos_payload
    if conjunto_id is not None and atual.get('conjunto_id') != conjunto_id:
        return
    conjunto = slides_store.obter(atual.get('conjunto_id'))
    if conjunto is None:
        parar()
        return
    _no_telao(payload(conjunto, atual.get('pos', 0)))


def exibir(conjunto_id, pos=0):
    """{'ok': True} ou {'erro': ...}."""
    conjunto = slides_store.obter(conjunto_id)
    if conjunto is None:
        return {'erro': tr('Esse conjunto de slides não existe mais.')}
    if not conjunto['slides']:
        return {'erro': tr('Escreva pelo menos um slide.')}
    _no_telao(payload(conjunto, pos))
    return {'ok': True}


def passo(direcao):
    """Na mão: avança (1) ou volta (-1). Na última tela, Próximo não dá a volta."""
    if not no_ar_na_mao():
        return {'ok': False, 'erro': tr('Não há slides passando na mão no telão.')}
    import telao
    p = display_state._avisos_payload
    total = len(p.get('telas') or [])
    nova = max(0, min(total - 1, p.get('pos', 0) + (1 if direcao > 0 else -1)))
    if nova != p.get('pos', 0):
        p['pos'] = nova
        socketio.emit('slides_ir', {'pos': nova})
        telao.broadcast_status()
    return {'ok': True, 'pos': nova, 'total': total}


def parar():
    import telao
    if no_ar():
        display_state._current_display_mode = 'blank'
        display_state._avisos_payload = None
        socketio.emit('avisos_parar', {})
        telao.set_public('blank')
        telao.broadcast_status()


# --- páginas e API ---------------------------------------------------------

@slides_bp.route('/slides')
@login_required
def slides_page():
    return render_template('slides.html', por_tela=slides_store.POR_TELA_PADRAO)


@slides_bp.route('/avisos')
def avisos_antigo():
    """Os Avisos em slides viraram um conjunto em /slides."""
    return redirect(url_for('slides.slides_page'))


@slides_bp.route('/api/slides')
@login_required
def api_listar():
    return jsonify({'conjuntos': slides_store.listar(), 'no_ar': resumo_no_ar(),
                    'temas': [{'id': t['id'], 'nome': t['nome']} for t in temas_store.listar()]})


@slides_bp.route('/api/slides', methods=['POST'])
@slides_bp.route('/api/slides/<int:conjunto_id>', methods=['PUT'])
@login_required
def api_salvar(conjunto_id=None):
    try:
        conjunto = slides_store.salvar(request.get_json(silent=True) or {}, conjunto_id)
    except ValueError as e:
        msg = tr('Dê um nome ao conjunto de slides.') if str(e) == 'nome' else tr('Já são muitos conjuntos de slides.')
        return jsonify({'erro': msg}), 400
    if conjunto is None:
        return jsonify({'erro': tr('Esse conjunto de slides não existe mais.')}), 404
    atualizar_no_ar(conjunto['id'])
    return jsonify({'conjunto': conjunto}), 200 if conjunto_id else 201


@slides_bp.route('/api/slides/<int:conjunto_id>', methods=['DELETE'])
@login_required
def api_apagar(conjunto_id):
    if no_ar() and display_state._avisos_payload.get('conjunto_id') == conjunto_id:
        parar()
    if not slides_store.apagar(conjunto_id):
        return jsonify({'erro': tr('Esse conjunto de slides não existe mais.')}), 404
    return jsonify({'ok': True})


@slides_bp.route('/api/slides/<int:conjunto_id>/exibir', methods=['POST'])
@login_required
def api_exibir(conjunto_id):
    dados = request.get_json(silent=True) or {}
    try:
        pos = int(dados.get('pos') or 0)
    except (TypeError, ValueError):
        pos = 0
    resultado = exibir(conjunto_id, pos)
    return jsonify(resultado), 200 if resultado.get('ok') else 400


@slides_bp.route('/api/slides/passo', methods=['POST'])
@login_required
def api_passo():
    dados = request.get_json(silent=True) or {}
    resultado = passo(-1 if (dados.get('direcao') or 1) < 0 else 1)
    return jsonify(resultado), 200 if resultado.get('ok') else 409


@slides_bp.route('/api/slides/parar', methods=['POST'])
@login_required
def api_parar():
    parar()
    return jsonify({'ok': True})
