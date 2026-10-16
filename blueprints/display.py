"""Núcleo de display: broadcast de imagem/vídeo, sincronização do monitor
de palco, persistência do estado exibido (URLs, letra, tema) e as páginas
/control, /monitor, /img. É a área mais entrelaçada do projeto — as
variáveis de display_state.py são lidas e escritas por praticamente todo
handler aqui.

Nota sobre app_context: alguns handlers salvam no banco numa thread de
fundo (threading.Thread), onde `current_app` (proxy de contexto) não
resolve sozinho — por isso capturam `current_app._get_current_object()`
(o app de verdade) antes de disparar a thread, e usam esse objeto
capturado dentro dela. Onde o app_context é usado só dentro do próprio
handler (sem thread), current_app.app_context() direto já basta."""
import json
import re
import threading
import time

from flask import Blueprint, current_app, jsonify, make_response, render_template, request
from flask_login import login_required
from flask_socketio import emit

import display_state
import telao
from blueprints.bible import handle_update_bible, parse_reference
from blueprints.gallery import get_current_image_path
from blueprints.lyrics import handle_update_lyrics
from connections import _get_monitor_sids, _skip_sids
from display_log import append_display_log
from extensions import db, socketio
from models import DisplayState, ImagePath, LyricsState, SavedUrls, StagedContent
from settings_store import load_settings, save_settings
from songs_store import get_song
from orders_store import current_key, mark_first_matching

display_bp = Blueprint('display', __name__)


# URLs salvas manualmente (favoritos do operador em control.html) —
# tabela SavedUrls (linha única), substitui urls.json.
def load_urls():
    row = SavedUrls.query.first()
    if not row:
        return {'url1': '', 'url2': '', 'url3': '', 'name1': '', 'name2': '', 'name3': ''}
    return {'url1': row.url1 or '', 'url2': row.url2 or '', 'url3': row.url3 or '',
            'name1': row.name1 or '', 'name2': row.name2 or '', 'name3': row.name3 or ''}


def save_urls(urls):
    row = SavedUrls.query.first()
    if not row:
        row = SavedUrls()
        db.session.add(row)
    row.url1 = urls.get('url1', '')
    row.url2 = urls.get('url2', '')
    row.url3 = urls.get('url3', '')
    for i in (1, 2, 3):
        key = f'name{i}'
        if key in urls:
            setattr(row, key, (urls.get(key) or '').strip()[:80])
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


# Rota para limpar as informações
@display_bp.route('/limpar')
def limpar():
    # Aqui você pode emitir um evento para limpar as informações na tela
    socketio.emit('limpar_tela')
    return 'Informações limpas!', 200


# Último caminho de imagem da galeria mostrado — tabela ImagePath (linha
# única), substitui image_paths.json. Fallback de 3º nível em /last_image.
def load_image_path():
    row = ImagePath.query.first()
    return {"image": row.image if row else None}

def save_image_path(image_path):
    row = ImagePath.query.first()
    if not row:
        row = ImagePath()
        db.session.add(row)
    row.image = image_path
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()

# Endpoint para salvar o caminho da imagem
@display_bp.route('/save_image_path', methods=['POST'])
@login_required
def save_image_path_endpoint():
    data = request.get_json()
    image_path = data.get('image_path')
    if image_path:
        save_image_path(image_path)
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error", "message": "Caminho da imagem não fornecido."}), 400

# Endpoint para obter a última imagem ou vídeo
def _is_static_media(url):
    if not url:
        return False
    return url.startswith('/static/') or \
        bool(re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', url, re.I))

@display_bp.route('/last_image', methods=['GET'])
def last_image_endpoint():
    # 1. Usa cache em memória (mais recente)
    if display_state._last_static_media_url:
        ext = display_state._last_static_media_url.lower().split('?')[0]
        media_type = 'video' if ext.endswith(('.mp4', '.webm', '.mov')) else 'image'
        return jsonify({'image_url': display_state._last_static_media_url, 'media_type': media_type}), 200
    # 2. Fallback: busca no banco — procura a primeira URL estática em url1 ou url2
    state = DisplayState.query.first()
    if state:
        for url in [state.url1, state.url2]:
            if _is_static_media(url):
                ext = (url or '').lower().split('?')[0]
                media_type = 'video' if ext.endswith(('.mp4', '.webm', '.mov')) else 'image'
                display_state._last_static_media_url = url
                return jsonify({'image_url': url, 'media_type': media_type}), 200
    data = load_image_path()
    return jsonify({'image_url': data.get('image'), 'media_type': 'image'}), 200


@display_bp.route('/control')
@login_required
def control():
    return render_template('control.html')

@display_bp.route('/monitor')
def monitor():
    return render_template('monitor.html')

# Rota para obter o estado atual do display
@display_bp.route('/get_display_state')
def get_display_state():
    import time as time_module

    # Verifica se o cache ainda é válido
    current_time = time_module.time()
    if display_state._display_state_cache['data'] and (current_time - display_state._display_state_cache['timestamp']) < display_state._cache_ttl:
        return jsonify(display_state._display_state_cache['data'])

    # Cache expirado ou vazio, busca do banco
    state = DisplayState.query.first()
    if state:
        result = {
            'url1': state.url1 or '',
            'url2': state.url2 or ''
        }
    else:
        result = {'url1': '', 'url2': ''}

    # Atualiza o cache
    display_state._display_state_cache['data'] = result
    display_state._display_state_cache['timestamp'] = current_time

    return jsonify(result)

def _persist_display_state(url1, url2=''):
    state = DisplayState.query.first()
    if not state:
        state = DisplayState(url1=url1, url2=url2)
        db.session.add(state)
    else:
        state.url1 = url1
        state.url2 = url2
    db.session.commit()
    # Atualiza também o cache em memória — api_monitor_sync() (botão
    # "Sincronizar Monitor" do /control) lê só daqui, sem cair pro banco;
    # sem isto, sincronizar o monitor não fazia nada na primeira letra
    # liberada numa sessão nova (cache ainda vazio), só funcionava pra
    # foto (handle_show_image já atualiza esse mesmo cache).
    display_state._display_state_cache['data'] = {'url1': url1, 'url2': url2}
    display_state._display_state_cache['timestamp'] = time.time()

# Rota para salvar o estado do display
@display_bp.route('/save_display_state', methods=['POST'])
@login_required
def save_display_state():
    data = request.json
    _persist_display_state(data.get('url1', ''), data.get('url2', ''))
    return jsonify({'status': 'success'})

# Rota para obter o estado atual das letras (música + seção)
@display_bp.route('/get_lyrics_state')
def get_lyrics_state():
    state = LyricsState.query.first()
    if state:
        return jsonify({
            'song_id': state.song_id,
            'section_index': state.section_index
        })
    return jsonify({'song_id': None, 'section_index': 0})

# Rota para salvar o estado das letras (música + seção)
@display_bp.route('/save_lyrics_state', methods=['POST'])
@login_required
def save_lyrics_state():
    data = request.json
    state = LyricsState.query.first()

    if not state:
        state = LyricsState(
            song_id=data.get('song_id'),
            section_index=data.get('section_index', 0)
        )
        db.session.add(state)
    else:
        state.song_id = data.get('song_id')
        state.section_index = data.get('section_index', 0)

    db.session.commit()
    current_app.logger.debug(f'💾 Estado das letras salvo: Música {state.song_id}, Seção {state.section_index}')
    return jsonify({'status': 'success'})

# Rota para exibir uma imagem específica
@display_bp.route('/img')
def serve_image():
    image_url = get_current_image_path()
    response = make_response(render_template('img.html', image_url=image_url))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@socketio.on('video_ended')
def handle_video_ended(data):
    emit('video_ended', {}, broadcast=True)


# Rota para salvar URLs no servidor
@display_bp.route('/save_urls', methods=['POST'])
@login_required
def save_urls_route():
    urls = request.json
    save_urls(urls)
    return jsonify({'status': 'success'})

# Rota para carregar as URLs salvas
@display_bp.route('/load_urls', methods=['GET'])
def load_urls_route():
    urls = load_urls()
    return jsonify(urls)

# Evento WebSocket para transmitir a URL da imagem
@socketio.on('show_image')
def handle_show_image(data):
    image_url = data['image_url']
    # use_active_mode: quem manda não sabe o modo (slideshow do /presenter)
    # — aplica o modo atual do servidor, como o Liberar já faz
    if data.get('use_active_mode'):
        mode = display_state.device_mode()
        if mode == 'monitor':
            handle_show_monitor_content({'url': image_url})
            return
        data = {**data, 'exclude_monitor': mode == 'public'}
    _end_live_follow_unless(image_url)
    real_app = current_app._get_current_object()

    # Imagem substituiu o vídeo no monitor: limpa estado de reprodução
    display_state._video_state['url'] = None
    display_state._video_state['paused'] = False
    display_state._video_state['position_offset'] = 0.0

    # Atualiza modo imediatamente (antes de qualquer retorno antecipado)
    display_state._last_image_url = image_url
    display_state._current_display_mode = 'image'
    current_app.logger.debug(f'🖼️ show_image recebido: {image_url} → modo=image')

    # Envia para clientes primeiro (não espera banco)
    emit('display_image', {'image_url': image_url}, broadcast=True, skip_sid=_skip_sids(data))
    append_display_log({'type': 'image', 'title': image_url})
    if data.get('exclude_monitor'):
        telao.diverge_monitor_from_public()
    elif not (_is_media_file(image_url) and telao.monitor_split_pane(image_url)):
        # Monitor dividido com lado de galeria: a foto entra nesse lado
        # (img.js dentro dele) e a divisão continua (ver monitor.js)
        telao.set_monitor(None)
    if telao.kind_of_url(image_url) == 'cifra':
        # A tela pública nunca mostra acordes (display_public.js troca a
        # rota da cifra pela letra limpa): público = letra, palco = cifra
        telao.set_public('lyrics', '/lyrics/display/public')
        if not data.get('exclude_monitor'):
            telao.set_monitor('cifra', image_url)
    else:
        telao.set_public_url(image_url)
    telao.broadcast_status()

    is_static_file = image_url.startswith('/static/') or \
        bool(re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', image_url, re.I))
    if is_static_file:
        # Mantém cache da última mídia estática — usado como fallback de
        # 'video' em api_current_display, então só faz sentido pra
        # arquivo estático de verdade, não pra rota como /clock.
        display_state._last_static_media_url = image_url

    # Atualiza cache
    display_state._display_state_cache['data'] = {'url1': image_url, 'url2': ''}
    display_state._display_state_cache['timestamp'] = time.time()

    # Persiste no banco pra sobreviver a um restart do servidor —
    # antes só persistia arquivo estático real; qualquer rota (/clock,
    # /img, /bible/display, qualquer botão do /control que chama
    # sendUrl()) nunca era salva, então reiniciar o servidor depois de
    # trocar pra uma dessas voltava a mostrar o que estava salvo antes
    # (achado ao vivo: clicar Relógio e reiniciar o servidor voltava
    # pra música exibida anteriormente).
    def save_async():
        with real_app.app_context():
            state = DisplayState.query.first()
            if not state:
                state = DisplayState(url1=image_url, url2='', media_type='image')
                db.session.add(state)
            else:
                state.url1 = image_url
                state.url2 = ''
                state.media_type = 'image'
            db.session.commit()

    threading.Thread(target=save_async, daemon=True).start()

@socketio.on('preload_image')
def handle_preload_image(data):
    """Repassa um aviso de 'próxima foto do slideshow' pras telas —
    puro broadcast, sem tocar no banco nem no display_state (não é uma
    troca de verdade, só um hint pra elas baixarem a imagem em segundo
    plano ANTES da troca real acontecer). Pedido do usuário: a tela
    pública só começava a baixar a foto no instante exato da troca, sem
    nenhum tempo de adiantamento — servir arquivo estático é leve, então
    adiantar esse download não pesa no servidor de forma nenhuma, só
    tira o atraso perceptível na hora de exibir de verdade."""
    emit('preload_image', {'url': data.get('url', '')}, broadcast=True)

@socketio.on('show_video')
def handle_show_video(data):
    video_url = data.get('video_url')
    _end_live_follow_unless(video_url)
    real_app = current_app._get_current_object()
    current_app.logger.debug(f'🎬 [show_video] recebido: {video_url}')
    if not video_url:
        return

    display_state._display_state_cache['data'] = {'url1': video_url, 'url2': '', 'media_type': 'video'}
    display_state._display_state_cache['timestamp'] = time.time()

    # Inicia novo vídeo: zera estado de reprodução
    display_state._video_state['url'] = video_url
    display_state._video_state['started_at'] = time.time()
    display_state._video_state['position_offset'] = 0.0
    display_state._video_state['paused'] = False

    display_state._last_static_media_url = video_url
    display_state._current_display_mode = 'video'
    # Um único emit — mandar de novo pro monitor (mesmo com skip_sid diferente)
    # entregava o evento duas vezes e as duas chamadas de .play() colidiam,
    # quebrando o vídeo no /monitor ("interrupted by a new load request").
    emit('display_video', {'video_url': video_url}, broadcast=True, skip_sid=_skip_sids(data))
    append_display_log({'type': 'image', 'title': video_url})
    if data.get('exclude_monitor'):
        telao.diverge_monitor_from_public()
    elif not telao.monitor_split_pane(video_url):
        telao.set_monitor(None)
    telao.set_public('video', video_url)
    telao.broadcast_status()

    def save_async():
        with real_app.app_context():
            state = DisplayState.query.first()
            if not state:
                state = DisplayState(url1=video_url, url2='', media_type='video')
                db.session.add(state)
            else:
                state.url1 = video_url
                state.url2 = ''
                state.media_type = 'video'
            db.session.commit()

    threading.Thread(target=save_async, daemon=True).start()


@socketio.on('toggle_video_pause')
def handle_toggle_video_pause(data):
    """Pausa ou retoma o vídeo no monitor (/img) e atualiza o estado central."""
    paused = bool(data.get('paused'))
    current_app.logger.debug(f'⏯️ [toggle_video_pause] paused={paused}')

    if display_state._video_state['url']:
        if paused and not display_state._video_state['paused']:
            # Pausando: congela posição atual no offset
            display_state._video_state['position_offset'] += time.time() - display_state._video_state['started_at']
            display_state._video_state['paused'] = True
        elif not paused and display_state._video_state['paused']:
            # Retomando: started_at = agora; offset preservado
            display_state._video_state['started_at'] = time.time()
            display_state._video_state['paused'] = False

    emit('video_pause', {'paused': paused}, broadcast=True, skip_sid=_skip_sids(data))


@socketio.on('restart_video')
def handle_restart_video(data):
    """Reinicia o vídeo atual no monitor (/img) do início."""
    current_app.logger.debug('⏮️ [restart_video] recebido')
    if display_state._video_state['url']:
        display_state._video_state['started_at'] = time.time()
        display_state._video_state['position_offset'] = 0.0
        display_state._video_state['paused'] = False
    emit('video_restart', {}, broadcast=True)


@socketio.on('seek_video')
def handle_seek_video(data):
    """Posiciona o vídeo do monitor em um tempo específico (segundos)."""
    try:
        target = max(0.0, float(data.get('time', 0)))
    except (TypeError, ValueError):
        return
    current_app.logger.debug(f'⏩ [seek_video] time={target:.2f}s')
    if display_state._video_state['url']:
        # Mantém estado de pause: se está pausado, só atualiza o offset; se está
        # tocando, redefine started_at para "agora" com o novo offset.
        display_state._video_state['position_offset'] = target
        display_state._video_state['started_at'] = time.time()
        # paused permanece como está
    emit('video_seek', {'time': target}, broadcast=True)


@display_bp.route('/video_state')
def video_state():
    """
    Retorna o estado atual de reprodução de vídeo. Usado por novas janelas /img
    para sincronizar a posição do vídeo com as janelas já abertas.
    """
    return jsonify({
        'url': display_state._video_state['url'],
        'position': display_state._video_current_position(),
        'paused': display_state._video_state['paused'],
    })


# ── Monitor de Palco ─────────────────────────────────────────────────────────

@socketio.on('show_monitor_content')
def handle_show_monitor_content(data):
    """Exibe URL/imagem apenas no /monitor, sem afetar o público."""
    url = data.get('url', '')
    _end_live_follow_unless(url)
    if _is_media_file(url) and telao.monitor_split_pane(url):
        # Monitor dividido com lado de galeria: só esse lado troca
        evento, chave = ('display_video', 'video_url') if telao.kind_of_url(url) == 'video' \
            else ('display_image', 'image_url')
        for sid in _get_monitor_sids():
            emit(evento, {chave: url}, to=sid)
        return
    telao.set_monitor_url(url)
    telao.broadcast_status()
    # O botão "Letra" manda o /monitor recarregar '/lyrics/display/public' num
    # iframe. Essa página, ao carregar do zero, busca /api/current-display pra
    # saber o que mostrar — e sem isto aqui, ela mostra o que foi exibido por
    # último de verdade ao público (ex: relógio), não a letra atual.
    # display_state._last_lyrics_payload some a cada restart do servidor,
    # então reconstrói a partir do payload exato persistido em
    # LyricsState.last_payload (mesmo fallback que /api/current-display
    # usa) — preserva tipo mixed/sheet e partitura, ao contrário da
    # reconstrução antiga (só title+text, sempre virava texto puro).
    if url == '/lyrics/display/public':
        with current_app.app_context():
            state = LyricsState.query.first()
            if state and state.last_payload:
                try:
                    display_state._last_lyrics_payload = json.loads(state.last_payload)
                    display_state._current_display_mode = 'lyrics'
                except (ValueError, TypeError):
                    pass
    for sid in _get_monitor_sids():
        emit('display_monitor_content', {'url': url}, to=sid)

@socketio.on('show_monitor_video')
def handle_show_monitor_video(data):
    """Exibe vídeo apenas no /monitor."""
    if telao.monitor_split_pane(data.get('video_url', '')):
        for sid in _get_monitor_sids():
            emit('display_video', {'video_url': data.get('video_url', '')}, to=sid)
        return
    telao.set_monitor('video', data.get('video_url', ''))
    telao.broadcast_status()
    for sid in _get_monitor_sids():
        emit('display_monitor_video', {'video_url': data.get('video_url', '')}, to=sid)

@socketio.on('show_monitor_pause')
def handle_show_monitor_pause(data):
    """Pausa/retoma vídeo apenas no /monitor."""
    for sid in _get_monitor_sids():
        emit('video_pause', {'paused': data.get('paused', False)}, to=sid)

@socketio.on('show_monitor_two_urls')
def handle_show_monitor_two_urls(data):
    """Exibe tela dividida apenas no /monitor."""
    telao.set_monitor_split(data.get('url1', ''), data.get('url2', ''))
    telao.broadcast_status()
    for sid in _get_monitor_sids():
        emit('display_two_urls', {'url1': data.get('url1', ''), 'url2': data.get('url2', '')}, to=sid)

@display_bp.route('/api/monitor/sync', methods=['POST'])
@login_required
def api_monitor_sync():
    """Sincroniza o /monitor com o estado público atual (vídeo ou display)."""
    sids = _get_monitor_sids()
    telao.set_monitor(None)
    telao.broadcast_status()
    if display_state._video_state['url']:
        pos = display_state._video_current_position()
        for sid in sids:
            socketio.emit('display_monitor_video', {'video_url': display_state._video_state['url']}, to=sid)
            socketio.emit('video_seek', {'time': pos}, to=sid)
            if display_state._video_state['paused']:
                socketio.emit('video_pause', {'paused': True}, to=sid)
    else:
        # Copia o que o público está vendo de verdade (telao.py) — antes
        # usava o cache da última fonte escolhida no /control, então uma
        # letra ou Bíblia liberada por outra página não entrava e o
        # monitor recebia a coisa errada
        url = telao.public_url()
        if url:
            for sid in sids:
                socketio.emit('display_monitor_content', {'url': url}, to=sid)
    return jsonify({'status': 'ok', 'monitors': len(sids)})


@socketio.on('blackout')
def handle_blackout(data):
    """Escurece ou restaura a tela de exibição"""
    display_state._blackout_active = bool(data.get('active', True))
    emit('blackout', {'active': display_state._blackout_active}, broadcast=True)
    telao.broadcast_status()

@socketio.on('show_image_zoom')
def handle_show_image_zoom(data):
    """
    Recebe requisição de zoom do presenter e reenvia aos monitores (/img).
    Espera payload: { image_url: str, zoom: float, origin?: {x,y} }
    """
    image_url = data.get('image_url')
    zoom = float(data.get('zoom', 1.0))
    origin = data.get('origin', None)
    pan = data.get('pan', None)
    try:
        current_app.logger.debug(f"[show_image_zoom] url={image_url} zoom={zoom} origin={origin} pan={pan}")
    except Exception:
        pass
    if not image_url:
        return
    emit('display_image_zoom', {'image_url': image_url, 'zoom': zoom, 'origin': origin, 'pan': pan}, broadcast=True)


# ── "Preparar vs. liberar" ────────────────────────────────────────────────
# Nenhuma das 4 páginas que mudavam a tela diretamente (letra, os dois
# fluxos de Bíblia, foto do /presenter) deve mais fazer isso sozinha —
# elas só "preparam" (stage_content); a mudança de verdade só acontece
# quando o /control libera (release_staged_content). Achado num incidente
# ao vivo (2026-08-16): um slideshow esquecido sobrescrevia a tela
# pública sozinha, e investigando isso o usuário percebeu que várias
# páginas tinham esse mesmo poder sem passar pelo /control. Um
# StagedContent por `kind` (não um slot único) — preparar uma foto não
# deve apagar uma letra que outra pessoa preparou em paralelo.
#
# release_staged_content chama direto os handlers reais de
# update_lyrics/update_bible/show_image (funções Python normais, o
# decorator @socketio.on não impede chamar diretamente) em vez de
# duplicar a lógica de emitir+persistir — assim qualquer correção
# futura neles também vale pro conteúdo liberado, e os testes de
# handler existentes continuam passando sem alteração nenhuma.
_KIND_LABELS = {'lyrics': 'Letra', 'bible': 'Bíblia', 'image': 'Foto'}


def _is_media_file(url):
    path = (url or '').split('?')[0]
    return path.startswith('/static/') or \
        bool(re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)$', path, re.I))


def _kind_of_url(url):
    """Tipo de preparar/liberar a que uma URL mandada ao telão pertence."""
    path = (url or '').split('?')[0]
    if path.startswith('/static/') or path == '/img' or \
            re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)$', path, re.I):
        return 'image'
    if path.startswith('/lyrics/display'):
        return 'lyrics'
    if path.startswith('/bible/display'):
        return 'bible'
    return None


def _end_live_follow_unless(*urls):
    """Ação direta no telão (fonte do /control, galeria, tela dividida):
    se ela leva o telão pra fora do tipo em live-follow, o próximo
    preparar desse tipo volta a pedir Liberar. _release_kind chama os
    mesmos handlers, mas regrava o live-follow logo depois."""
    kind = display_state._live_follow_kind
    if kind and any(_kind_of_url(u) != kind for u in urls):
        display_state._live_follow_kind = None


# (culto, item) marcado sozinho por último (ver _marcar_feito_no_ar): cada
# seção da música / versículo que vai ao ar chama de novo, e não pode
# marcar a 2ª vez que a mesma música aparece na ordem.
_ultimo_feito_auto = None


def _mesma_passagem(item, ref_no_ar):
    """Item bíblico da ordem cobre o versículo que foi ao ar? ('Romanos
    10:14-17' cobre 'Romanos 10:15'; 'Salmos 23' cobre qualquer verso)."""
    if not (item.get('isBible') or '/bible/control/' in (item.get('url') or '')):
        return False
    texto = item.get('reference') or re.sub(r'^\W+', '', item.get('title') or '')
    ref_item = parse_reference(texto) if texto else None
    if not ref_item or (ref_item['book_abbrev'], ref_item['chapter']) != (ref_no_ar['book_abbrev'], ref_no_ar['chapter']):
        return False
    if ref_item['verse_start'] is None or ref_no_ar['verse_start'] is None:
        return True
    return ref_item['verse_start'] <= ref_no_ar['verse_start'] <= ref_item['verse_end']


def _marcar_feito_no_ar(kind, payload):
    """Música ou leitura foi ao telão: marca o item na ordem do culto atual
    de hoje (view/order). Nunca derruba o telão se der errado."""
    global _ultimo_feito_auto
    try:
        if kind == 'lyrics' and payload.get('songId') is not None:
            url = f"/lyrics/{payload['songId']}"
            match = lambda item: (item.get('url') or '').split('?')[0] == url
        elif kind == 'bible' and payload.get('reference'):
            ref = parse_reference(str(payload['reference']))
            if not ref:
                return
            match = lambda item: _mesma_passagem(item, ref)
        else:
            return
        from datetime import date
        key = current_key(date.today().isoformat())
        ultimo_key, ultimo_id = _ultimo_feito_auto or (None, None)
        marcado = mark_first_matching(key, match, skip_if=ultimo_id if ultimo_key == key else None)
        # Algo fora da ordem foi ao ar: zera, pra próxima vez que a música
        # voltar contar como a próxima ocorrência dela na ordem
        _ultimo_feito_auto = (key, marcado) if marcado else None
    except Exception:
        current_app.logger.exception('Falha ao marcar item da ordem como feito')


def _release_kind(kind, payload):
    """Faz o kind ir ao ar de verdade (chamando o handler real) e marca
    esse kind como o "live-follow" atual — ver display_state._live_follow_kind.
    Compartilhada entre o release explícito (clique em Liberar, seja pelo
    card do /control ou pelo banner nas próprias páginas — ver
    release_banner.js) e o auto-release do live-follow em
    handle_stage_content, pra não duplicar a lógica de qual handler
    chamar pra cada kind.

    Lê o modo (Público/Monitor) da máquina que liberou direto de
    display_state.device_mode() — não recebe isso como parâmetro de
    propósito, já que o modo é uma decisão do /control daquela máquina que
    precisa valer igual não importa de qual página a liberação partiu (ver
    comentário de _device_modes em display_state.py). Vale
    pra kind='image' (mecanismo original, também usado pelas ações
    nativas do /control: URL, galeria) e kind='lyrics'. Bíblia ainda não
    tem esse suporte — o monitor nunca teve nenhum jeito de mostrar
    bíblia, nem antes da existência de preparar/liberar, então
    precisaria ser construído do zero antes de sequer cogitar os modos."""
    mode = display_state.device_mode()
    exclude_monitor = mode == 'public'
    monitor_only = mode == 'monitor'

    if kind == 'lyrics':
        song_id = payload.get('songId')
        section_index = payload.get('sectionIndex')
        # URL do iframe do monitor pra esta letra — host=monitor faz
        # display.js (a página /lyrics/display) se identificar como
        # 'monitor' no socket (ver display.js), pra _get_monitor_sids()
        # conseguir excluir/direcionar ela junto com o /monitor de
        # verdade nos dois branches abaixo.
        lyrics_url = None
        if song_id is not None and section_index is not None:
            lyrics_url = f'/lyrics/display?song_id={song_id}&section={section_index}&host=monitor'

        split_pane = telao.monitor_split_pane(lyrics_url) if lyrics_url else None
        if monitor_only and split_pane:
            # Monitor dividido com lado de cifra/letra: a seção nova vai só
            # pras páginas dentro do monitor (update_lyrics; o /monitor em si
            # não escuta esse evento) e a divisão continua. Antes o
            # show_monitor_content trocava o monitor inteiro pela cifra.
            for sid in _get_monitor_sids():
                emit('update_lyrics', payload, to=sid)
        elif monitor_only:
            # Só empurra pro iframe do monitor via show_monitor_content
            # (mesmo mecanismo que o botão de URL fixa "Letra" já usa em
            # Modo Monitor) — nunca chama handle_update_lyrics, então
            # público/OBS nem ficam sabendo que isso aconteceu.
            if lyrics_url:
                handle_show_monitor_content({'url': lyrics_url})
        else:
            emit_data = dict(payload)
            if exclude_monitor:
                emit_data['exclude_monitor'] = True
            handle_update_lyrics(emit_data)
            # Persiste o DisplayState (restauro do monitor ao recarregar —
            # ver loadDisplayState()/loadLyricsState() em monitor.js) só
            # quando o monitor de fato deveria saber desta mudança. Com
            # Modo Público (exclude_monitor), o monitor não recebeu a
            # atualização ao vivo — gravar aqui faria ele "pular" pra essa
            # letra na próxima vez que recarregar, o que quebraria o
            # "congela" que o modo promete.
            if lyrics_url and not exclude_monitor and not split_pane:
                with current_app.app_context():
                    _persist_display_state(lyrics_url, '')
    elif kind == 'bible':
        handle_update_bible(payload)
    elif kind == 'image':
        if monitor_only:
            handle_show_monitor_content({'url': payload.get('image_url', '')})
        elif exclude_monitor:
            handle_show_image({**payload, 'exclude_monitor': True})
        else:
            handle_show_image(payload)

    _marcar_feito_no_ar(kind, payload)
    display_state.follow_confirma(kind)
    emit('content_released', {'kind': kind}, broadcast=True)
    telao.broadcast_status()


@socketio.on('stage_content')
def handle_stage_content(data):
    kind = data.get('kind')
    payload = data.get('payload')
    current_app.logger.debug(f'📋 Recebido stage_content: kind={kind}')
    if kind not in _KIND_LABELS or not payload:
        return
    label = data.get('label') or _KIND_LABELS[kind]

    # Live-follow: esse kind já foi confirmado ao vivo antes (por um
    # Liberar explícito, nesta mesma sessão) — navegar dentro dele (outra
    # seção da mesma letra, outro verso, outra foto) vai direto ao ar, sem
    # pedir confirmação a cada clique. Só reseta ao liberar um kind
    # DIFERENTE (ver _release_kind) — trocar de tipo continua pedindo
    # confirmação explícita, o que preserva a proteção original pra quem
    # ainda não tiver confirmado aquele tipo nesta sessão (ex: uma foto
    # nunca precisa ser "a mesma coisa" que o relógio, já que ações
    # nativas do /control não tocam o live-follow — ver display_state.py).
    if display_state.follow_inclui(kind):
        with current_app.app_context():
            staged = db.session.get(StagedContent, kind)
            if staged:
                db.session.delete(staged)
                db.session.commit()
        _release_kind(kind, payload)
        return

    with current_app.app_context():
        staged = db.session.get(StagedContent, kind)
        if staged is None:
            staged = StagedContent(kind=kind)
            db.session.add(staged)
        staged.payload = payload
        staged.label = label
        db.session.commit()
    emit('content_staged', {'kind': kind, 'label': label}, broadcast=True)
    telao.broadcast_status()


@socketio.on('release_staged_content')
def handle_release_staged_content(data):
    kind = data.get('kind')
    current_app.logger.debug(f'🚀 Recebido release_staged_content: kind={kind}')
    with current_app.app_context():
        staged = db.session.get(StagedContent, kind)
        if not staged:
            return
        payload = staged.payload
        db.session.delete(staged)
        db.session.commit()

    _release_kind(kind, payload)


@socketio.on('set_display_mode')
def handle_set_display_mode(data):
    """Emitido pelo /control ao escolher Os dois / Só público / Só monitor
    (setModeChoice em control.js) — grava o modo DESTA máquina em
    display_state._device_modes, que _release_kind lê pra QUALQUER
    liberação feita daqui, não importa se veio do card do /control ou do
    banner nas próprias páginas (release_banner.js não tem acesso às
    variáveis JS do /control, que fica numa aba/página diferente).

    Também reseta o live-follow — trocar de modo é uma troca de contexto
    igual trocar de tipo: sem isto, um live-follow em andamento continuaria
    indo pra tela antiga até a próxima liberação explícita."""
    display_state.set_device_mode('monitor' if data.get('monitor_only')
                                  else 'public' if data.get('exclude_monitor') else 'all')
    display_state._live_follow_kind = None
    telao.broadcast_status()


@socketio.on('slideshow_state')
def handle_slideshow_state(data=None):
    """O /control avisa quando o slideshow começa/para (o timer roda no
    navegador dele) — pra barrinha do telão mostrar e poder parar."""
    data = data or {}
    telao.set_slideshow(request.sid, bool(data.get('running')),
                        interval=data.get('interval'), count=data.get('count'))
    telao.broadcast_status()


@socketio.on('stop_slideshow')
def handle_stop_slideshow(data=None):
    """Botão "parar" da barrinha: manda o /control que roda o slideshow parar."""
    telao.set_slideshow(None, False)
    emit('slideshow_stop', {}, broadcast=True)
    telao.broadcast_status()


@socketio.on('telao_ping')
def handle_telao_ping(data=None):
    """Batimento da barrinha do telão (telao_bar.js): responder em até 4s
    = servidor alcançável. Sem resposta, a página avisa "Sem conexão"."""
    return {'ok': True}


@socketio.on('stop_live_follow')
def handle_stop_live_follow(data=None):
    """Botão "parar" da barrinha do telão: o próximo preparar volta a
    pedir Liberar, mesmo do tipo que estava acompanhando ao vivo."""
    display_state._live_follow_kind = None
    telao.broadcast_status()


@display_bp.route('/api/telao-status')
@login_required
def api_telao_status():
    """Resumo do telão pra barrinha "No ar / Preparado" (telao.py)."""
    return jsonify({**telao.build_status(), 'mode': display_state.device_mode()})


@socketio.on('discard_staged_content')
def handle_discard_staged_content(data):
    kind = data.get('kind')
    with current_app.app_context():
        staged = db.session.get(StagedContent, kind)
        if staged:
            db.session.delete(staged)
            db.session.commit()
    emit('content_discarded', {'kind': kind}, broadcast=True)
    telao.broadcast_status()


# Pro /control buscar o que já estiver preparado ao carregar a página —
# não dá pra confiar só no broadcast ao vivo de content_staged, o
# /control pode ser aberto DEPOIS de algo já ter sido preparado (caso
# real: operador prepara antes de ir até o notebook do /control).
@display_bp.route('/api/staged-content')
def api_staged_content():
    items = StagedContent.query.all()
    return jsonify({
        s.kind: {'label': s.label, 'updated_at': s.updated_at.isoformat() if s.updated_at else None}
        for s in items
    })


# Evento WebSocket para transmitir duas URLs de imagem
@socketio.on('show_two_urls')
def handle_show_two_urls(data):
    real_app = current_app._get_current_object()

    url1 = data['url1'] or ''
    url2 = data['url2'] or ''
    _end_live_follow_unless(url1, url2)

    # Detecta media_type de url1 pela extensão
    url1_lower = url1.lower().split('?')[0]
    if url1_lower.endswith(('.mp4', '.webm', '.mov')):
        media_type = 'video'
    else:
        media_type = 'image'

    # Tela dividida substituiu o vídeo: limpa estado de reprodução
    display_state._video_state['url'] = None
    display_state._video_state['paused'] = False
    display_state._video_state['position_offset'] = 0.0

    # Envia para clientes primeiro (não espera banco)
    emit('display_two_urls', {'url1': url1, 'url2': url2}, broadcast=True, skip_sid=_skip_sids(data))
    append_display_log({'type': 'image', 'title': url1 + (' + ' + url2 if url2 else '')})
    if not data.get('exclude_monitor'):
        telao.set_monitor_split(url1, url2)  # a tela pública não divide
        telao.broadcast_status()

    # Para salvar no banco, substitui '/img' pela URL real da última imagem salva
    def _resolve_img_url(u):
        if u != '/img':
            return u
        cached = display_state._display_state_cache.get('data') or {}
        if cached.get('url1') and cached['url1'] != '/img':
            return cached['url1']
        try:
            with real_app.app_context():
                state = DisplayState.query.first()
                if state and state.url1 and state.url1 != '/img':
                    return state.url1
        except Exception:
            pass
        return ''

    def save_async():
        save_url1 = _resolve_img_url(url1)
        save_url2 = _resolve_img_url(url2)
        # Não sobrescreve o banco se ambas as URLs são rotas sem valor persistível
        if not save_url1 and not save_url2:
            return
        with real_app.app_context():
            state = DisplayState.query.first()
            if not state:
                state = DisplayState(url1=save_url1, url2=save_url2, media_type=media_type)
                db.session.add(state)
            else:
                if save_url1:
                    state.url1 = save_url1
                state.url2 = save_url2
                state.media_type = media_type
            db.session.commit()

    threading.Thread(target=save_async, daemon=True).start()

# Evento WebSocket para transmitir a URL
@socketio.on('send_url')
def handle_send_url(url):
    emit('update_url', {'url': url}, broadcast=True)

@display_bp.route('/api/current-display')
def api_current_display():
    # Botão Letra/Cifra do /control manda a ROTA da letra (show_image com
    # /lyrics/display…): quem abre do zero (monitor, prévia, telão
    # recarregado) precisa da letra atual, não da própria rota — senão a
    # página tentava abrir a si mesma num iframe e ficava em branco
    if display_state._current_display_mode == 'image' and \
            (display_state._last_image_url or '').startswith('/lyrics/display') and \
            display_state._last_lyrics_payload:
        return jsonify({'mode': 'lyrics', **display_state._last_lyrics_payload})
    if display_state._current_display_mode == 'image' and display_state._last_image_url:
        is_static = display_state._last_image_url.startswith('/static/') or \
            bool(re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', display_state._last_image_url, re.I))
        return jsonify({'mode': 'image', 'image_url': display_state._last_image_url, 'is_static': is_static})
    if display_state._current_display_mode == 'video' and display_state._last_static_media_url:
        return jsonify({'mode': 'video', 'video_url': display_state._last_static_media_url})
    if display_state._current_display_mode == 'lyrics' and display_state._last_lyrics_payload:
        return jsonify({'mode': 'lyrics', **display_state._last_lyrics_payload})

    # Estado em memória (display_state.*) é volátil e some a cada
    # restart do servidor — daqui pra baixo é reconstrução a partir do
    # banco. DisplayState.url1 é a fonte da verdade de "o que foi
    # exibido por último" através de TODOS os modos: rotas genéricas
    # (handle_show_image — /clock, /img, /bible/display, qualquer botão
    # do /control que manda uma única URL) e letra/partitura (lyrics_2.js
    # chama /save_display_state a cada seção carregada). Usa ela pra
    # decidir QUAL reconstrução fazer, em vez de sempre cair na de letra
    # — bug real encontrado nesta sessão: trocar pro Relógio e reiniciar
    # o servidor voltava a mostrar a música, porque a reconstrução de
    # letra "vencia" incondicionalmente qualquer outro modo.
    display = DisplayState.query.first()
    url1 = (display.url1 if display else '') or ''

    if url1.startswith('/lyrics/display'):
        # LyricsState.last_payload guarda o payload exato do último
        # update_lyrics (JSON), reconstrução fiel (inclusive
        # partitura/tipo mixed) — a reconstrução antiga a partir só de
        # song_id+section_index sempre virava 'type':'text' mesmo pra
        # seção mista/partitura, e deixava o marcador
        # 🎼 PARTITURA_INTEGRADA_... cru no texto.
        state = LyricsState.query.first()
        if state and state.last_payload:
            try:
                payload = json.loads(state.last_payload)
                return jsonify({'mode': 'lyrics', **payload})
            except (ValueError, TypeError):
                pass
        # Último recurso: reconstrói só o texto a partir de song_id/
        # section_index (não recupera partitura/tipo mixed) — só pra
        # dado salvo antes desta persistência existir.
        if state and state.song_id:
            song = get_song(state.song_id)
            if song and state.section_index < len(song['sections']):
                section = song['sections'][state.section_index]
                return jsonify({
                    'mode': 'lyrics',
                    'title': section['title'],
                    'text': section['text'][0],
                    'type': 'text',
                    'theme': None
                })
    elif url1:
        if display.media_type == 'video':
            return jsonify({'mode': 'video', 'video_url': url1})
        is_static = url1.startswith('/static/') or \
            bool(re.search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', url1, re.I))
        return jsonify({'mode': 'image', 'image_url': url1, 'is_static': is_static})

    return jsonify({'mode': 'blank'})

@socketio.on('set_display_bg')
def handle_set_display_bg(data):
    dark = data.get('dark', True)
    settings = load_settings()
    settings['display_bg_dark'] = dark
    save_settings(settings)
    emit('set_display_bg', data, broadcast=True)

@display_bp.route('/api/display-bg')
def get_display_bg():
    settings = load_settings()
    return jsonify({'dark': settings.get('display_bg_dark', True)})
