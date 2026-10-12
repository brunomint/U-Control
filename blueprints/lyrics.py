"""Letras de músicas: páginas de apresentação/presenter, API de seções e
tema, e os handlers de socket que transmitem a seção atual pro display.
update_lyrics é o único ponto de contato com o estado compartilhado de
display (display_state.py) — escreve _last_lyrics_payload/
_current_display_mode, lidos por api_current_display (que fica em
blueprints/display.py, Fase 3.23, por lidar com os 3 modos de exibição,
não só letras)."""
import json
import logging

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required
from flask_socketio import emit

import display_state
from connections import _skip_sids
from display_log import append_display_log
from extensions import db, socketio
from models import LyricsState
from orders_store import load_orders
from songs_store import get_song, set_theme, touch_last_played

logger = logging.getLogger('ucontrol')

lyrics_bp = Blueprint('lyrics', __name__)


@lyrics_bp.route('/lyrics/<int:song_id>')
@login_required
def lyrics(song_id):
    """Exibe as letras de uma música."""
    # get_song()+touch_last_played() em vez de load_songs()+save_songs()
    # com a lista inteira: essa rota é visitada a cada troca de música, e
    # carregar/resalvar as 371 músicas só pra atualizar o last_played de 1
    # era proporcional ao total de músicas (~2.3s), não ao trabalho real
    # (1 linha). Achado a partir do relato "cifras ficam lentas trocando
    # de música" (2026-08-15).
    song = get_song(song_id)
    if not song:
        return "Música não encontrada", 404

    touch_last_played(song_id)

    # Detecta automaticamente a ordem que contém esta música
    order_date = request.args.get('order')
    if not order_date:
        from datetime import date as date_cls
        today = str(date_cls.today())
        orders = load_orders()
        song_url = f'/lyrics/{song_id}'
        matching_dates = []
        for d, order in orders.items():
            for item in order.get('itens', []):
                if item.get('url') == song_url:
                    matching_dates.append(d)
                    break
        if matching_dates:
            # Prefere a data mais próxima de hoje (futuras primeiro, depois passadas)
            future = sorted([d for d in matching_dates if d >= today])
            past   = sorted([d for d in matching_dates if d < today], reverse=True)
            order_date = (future + past)[0]

    # Estado real de visibilidade (não assume True) — ver LyricsState.visible.
    lyrics_state = LyricsState.query.first()
    lyrics_visible = lyrics_state.visible if lyrics_state else True

    return render_template('lyrics.html', song=song, order_date=order_date, lyrics_visible=lyrics_visible)

@lyrics_bp.route('/api/lyrics/visible')
def api_lyrics_visible():
    """Estado do botão Esconder/Mostrar (LyricsState.visible) — as telas
    (tela pública, Bíblia (tela)) leem ao abrir, pra não voltarem a mostrar
    o texto que o operador escondeu. Sem login, como as próprias telas."""
    state = LyricsState.query.first()
    return jsonify({'visible': state.visible if state else True})


@lyrics_bp.route('/api/lyrics/<int:song_id>')
def api_lyrics(song_id):
    """Retorna os dados completos da música em JSON (para API)."""
    song = get_song(song_id)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404

    return jsonify(song)

@lyrics_bp.route('/api/lyrics/<int:song_id>/theme', methods=['POST'])
@login_required
def set_song_theme(song_id):
    data = request.get_json()
    if not set_theme(song_id, data.get('theme')):  # None limpa o tema
        return jsonify({'error': 'not found'}), 404
    return jsonify({'ok': True})

@lyrics_bp.route('/section/<int:song_id>/<int:section_index>')
def section(song_id, section_index):
    """Exibe uma seção específica da música."""
    song = get_song(song_id)
    if not song or section_index < 0 or section_index >= len(song['sections']):
        return jsonify({'error': 'Seção inválida'}), 404

    section = song['sections'][section_index]
    socketio.emit('update_lyrics', {
        'title': section['title'],
        'text': section['text'][0]
    })

    return jsonify({
        'title': section['title'],
        'text': section['text'][0]
    })

@lyrics_bp.route('/lyrics_data/<int:song_id>')
def lyrics_data(song_id):
    """Retorna os dados da primeira seção da música."""
    song = get_song(song_id)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404

    section = song['sections'][0]
    return jsonify({
        'title': section['title'],
        'text': section['text'][0]
    })

@lyrics_bp.route('/full-lyrics/<int:song_id>')
def full_lyrics(song_id):
    """Retorna as letras completas da música."""
    song = get_song(song_id)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404

    full_lyrics_text = "\n".join([section['text'][0] for section in song['sections']])
    return jsonify({'lyrics': full_lyrics_text})

@lyrics_bp.route('/lyrics/display')
def lyrics_display():
    """Exibe a tela de visualização das letras."""
    # Verifica se há parâmetros de URL para carregar música/seção específica
    song_id = request.args.get('song_id', type=int)
    section_index = request.args.get('section', type=int, default=0)

    return render_template('display.html', song_id=song_id, section_index=section_index)

@lyrics_bp.route('/lyrics/display/public')
def lyrics_display_Public():
    """Exibe a tela de visualização das letras para o público."""
    return render_template('display_public.html')

@lyrics_bp.route('/lyrics/display/obs')
def lyrics_display_obs():
    """Overlay transparente para OBS/streaming (Browser Source)."""
    return render_template('display_obs.html')


@lyrics_bp.route('/presenter')
@login_required
def presenter():
    return render_template('presenter.html')


def mostrar_se_escondido():
    """Conteúdo novo indo ao ar (seção de música ou versículo) mostra o
    texto de novo: o "Esconder" vale pro que está no telão naquela hora.
    Antes ficava escondido pra sempre — esconder a letra e depois mandar
    um versículo deixava a tela preta, e a página da Bíblia nem tem o
    botão Mostrar."""
    try:
        state = LyricsState.query.first()
        if state is None or state.visible is not False:
            return
        state.visible = True
        db.session.commit()
    except Exception:
        logger.exception('Falha ao mostrar o texto de novo')
        return
    emit('lyrics_visibility_changed', {'visible': True}, broadcast=True)


# Evento WebSocket para transmitir letras de músicas
@socketio.on('update_lyrics')
def handle_update_lyrics(data):
    logger.debug(f'📨 Recebido update_lyrics: {data.get("title", "Sem título")}')
    mostrar_se_escondido()
    display_state._last_lyrics_payload = data
    display_state._current_display_mode = 'lyrics'
    # Persiste o payload exato (não só em memória) — display_state
    # some a cada restart do servidor; sem isto, api_current_display cai
    # num fallback que reconstrói a partir de song_id+section_index e
    # perde o tipo mixed/sheet (sempre virava texto puro, com o
    # marcador 🎼 PARTITURA_INTEGRADA_... cru aparecendo na tela).
    try:
        with current_app.app_context():
            state = LyricsState.query.first()
            if state is None:
                state = LyricsState()
                db.session.add(state)
            state.last_payload = json.dumps(data)
            db.session.commit()
    except Exception:
        logger.exception('Falha ao persistir last_payload de update_lyrics')
    emit('update_lyrics', data, broadcast=True, skip_sid=_skip_sids(data))
    import telao
    if data.get('exclude_monitor'):
        telao.diverge_monitor_from_public()
    telao.set_public('lyrics', '/lyrics/display/public')
    telao.broadcast_status()

# Evento WebSocket para mudança de seção
@socketio.on('section_changed')
def handle_section_changed(data):
    song_id = data.get('songId')
    logger.debug(f'📨 Recebido section_changed: Song {song_id}, Section {data.get("sectionIndex")}')
    song = get_song(song_id)
    song_title = song['title'] if song else str(song_id)
    append_display_log({'type': 'song', 'title': song_title, 'url': f'/lyrics/{song_id}'})
    emit('section_changed', data, broadcast=True)

# Evento WebSocket para mostrar/esconder letras
@socketio.on('toggle_lyrics_visibility')
def handle_toggle_lyrics_visibility(data):
    visible = data.get('visible', True)
    logger.debug(f'👁️ Toggle letras: {"Mostrar" if visible else "Esconder"}')
    # Persiste — sem isto, recarregar /lyrics/<id> sempre assumia visible=True,
    # dessincronizando o botão do que a tela pública estava mostrando de fato.
    try:
        with current_app.app_context():
            state = LyricsState.query.first()
            if state is None:
                state = LyricsState()
                db.session.add(state)
            state.visible = visible
            db.session.commit()
    except Exception:
        logger.exception('Falha ao persistir visible de toggle_lyrics_visibility')
    emit('lyrics_visibility_changed', {'visible': visible}, broadcast=True)
