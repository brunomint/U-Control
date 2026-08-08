from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    make_response,
)
from werkzeug.routing import BaseConverter
from flask_socketio import emit, join_room
from flask_login import login_required
from datetime import datetime, date
import os
import json
import re
import threading
import requests
import time
import webbrowser
from pychord import Chord
from pptx import Presentation
import socket
import qrcode
from bs4 import BeautifulSoup
from zeroconf import ServiceInfo, Zeroconf
import logging
from logging.handlers import RotatingFileHandler

from extensions import db, migrate, login_manager, socketio
from models import User, DisplayState, LyricsState
from display_log import append_display_log
from settings_store import load_settings, save_settings
from blueprints.countdown import countdown_bp
from blueprints.ticker import ticker_bp
from blueprints.auth import auth_bp
from blueprints.bible import bible_bp, generate_bible_url
from blueprints.cifras import cifras_bp
from songs_store import load_songs, save_songs
from blueprints.songs import songs_bp
from network_utils import PORTA, obter_endereco_ip
from blueprints.utils import utils_bp
from blueprints.gallery import gallery_bp, get_current_image_path
from orders_store import load_orders
from blueprints.orders import orders_bp
from blueprints.agenda import agenda_bp
import display_state
import blueprints.screen_share  # noqa: F401 — importado só pelo efeito colateral de registrar os handlers de socket
from connections import _get_monitor_sids, _skip_sids

logger = logging.getLogger('ucontrol')


def _setup_logging(app):
    """Configura logging estruturado: console sempre, arquivo rotativo em instance/."""
    level = logging.DEBUG if os.getenv('UCONTROL_DEBUG') == '1' else logging.INFO
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    os.makedirs(app.instance_path, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(app.instance_path, 'ucontrol.log'),
        maxBytes=1_000_000,
        backupCount=4,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


class DateSlugConverter(BaseConverter):
    """Converte datas no formato YYYY-MM-DD (evita conflito com /agenda/edit)."""
    regex = r"\d{4}-\d{2}-\d{2}"


def data_pt(date_str):
    """Formata YYYY-MM-DD como 'Quarta-feira, 8 de julho de 2026'."""
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira',
                'Sexta-feira', 'Sábado', 'Domingo']
        meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        return f"{dias[dt.weekday()]}, {dt.day} de {meses[dt.month - 1]} de {dt.year}"
    except Exception:
        return date_str

texto = "Acessar ucontrol"
MDNS_NOME = "ucontrol"
MDNS_DOMINIO = f"{MDNS_NOME}.local."


def _load_or_create_secret_key(app):
    """Carrega a SECRET_KEY de instance/secret_key, gerando uma vez se não
    existir. Antes era gerada a cada start (os.urandom direto), o que
    invalidava a sessão de todo mundo a cada restart/deploy."""
    os.makedirs(app.instance_path, exist_ok=True)
    key_path = os.path.join(app.instance_path, 'secret_key')
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            return f.read()
    key = os.urandom(24)
    with open(key_path, 'wb') as f:
        f.write(key)
    os.chmod(key_path, 0o600)
    return key


def create_app(config=None):
    """Cria e configura a instância do Flask. Chamada uma vez, na importação
    do módulo — as 114 rotas e 36 handlers de socket abaixo continuam
    registrados nos objetos globais app/socketio/db, sem precisar mover
    nenhuma. Se config vier, sobrescreve os defaults (usado pelos testes)."""
    app = Flask(__name__)
    _setup_logging(app)

    app.url_map.converters["dateslug"] = DateSlugConverter
    app.template_filter('data_pt')(data_pt)

    app.secret_key = _load_or_create_secret_key(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Caminho para o banco de dados
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_NAME'] = 'session'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False

    if config is None and os.getenv('UCONTROL_TESTING') == '1':
        config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'TESTING': True}
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1000000,
        allow_upgrades=True,
        transports=['polling', 'websocket'],
    )

    if app.config.get('TESTING'):
        # Banco em memória dos testes: recriado do zero a cada processo, não
        # faz sentido versionar com migration. Fora de teste (dev ou
        # produção), o schema vem só de `flask db upgrade` (migrations/).
        with app.app_context():
            db.create_all()

    app.register_blueprint(countdown_bp)
    app.register_blueprint(ticker_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bible_bp)
    app.register_blueprint(cifras_bp)
    app.register_blueprint(songs_bp)
    app.register_blueprint(utils_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(agenda_bp)

    return app


app = create_app()




# QR CODE

def gerar_qrcodes(rotas):
    ip_local = obter_endereco_ip()

    # Caminho dinâmico para a pasta static/qrcodes
    caminho_pasta = os.path.join(os.getcwd(), "static", "qrcodes")
    os.makedirs(caminho_pasta, exist_ok=True)  # Garante que a pasta exista

    for rota in rotas:
        url_completa = f"http://{ip_local}:{PORTA}/{rota}"
        nome_arquivo = f"{rota.replace('/', '_')}_qr_code.png"

        caminho_arquivo = os.path.join(caminho_pasta, nome_arquivo)

        # Gerar o QR Code e salvar
        qr_code = qrcode.make(url_completa)
        qr_code.save(caminho_arquivo)
        logger.info(f"QR Code para '{url_completa}' salvo em: {caminho_arquivo}")

# Lista de rotas para as quais você quer gerar QR Codes
rotas = ["control", "songs", "lyrics/display", "monitor", "img", "presenter", "help", "order", "view", "bible", "bible/display"]

def gerar_links(rotas):
    ip_local = obter_endereco_ip()
    links = []

    for rota in rotas:
        if rota == "/":
            url_completa = f"http://{ip_local}:{PORTA}/"
        else:
            url_completa = f"http://{ip_local}:{PORTA}/{rota}"
        links.append(url_completa)

    return links

# Gerar os QR Codes
gerar_qrcodes(rotas)










# Caminho do arquivo para salvar as URLs
URLS_FILE = 'urls.json'

# Função para carregar URLs do arquivo JSON
def load_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, 'r') as file:
            return json.load(file)
    return {'url1': '', 'url2': '', 'url3': ''}

# Função para salvar URLs no arquivo JSON
def save_urls(urls):
    with open(URLS_FILE, 'w') as file:
        json.dump(urls, file)







@app.route('/view')
def view_song_order():
    order_date = request.args.get('order')
    return render_template('view_song_order.html', order_date=order_date)

# Rota para visualizar ordem de culto por data (compartilhável)
@app.route('/view/order/<date>')
def view_order_by_date(date):
    """Visualiza uma ordem de culto específica por data"""
    orders = load_orders()
    order = orders.get(date)
    if not order:
        return render_template('view_order.html', date=date, order=None, not_found=True)
    
    # Gera URLs de controle para itens bíblicos
    if order and order.get('itens'):
        for item in order['itens']:
            if item.get('isBible'):
                item['bible_url'] = generate_bible_url(item.get('reference', ''))
    
    return render_template('view_order.html', date=date, order=order, not_found=False)

@app.route('/view/<int:song_id>')
def view_song(song_id):
    """Exibe os detalhes de uma música."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
    if not song:
        return "Música não encontrada!", 404

    # Verifica se há parâmetro de data na URL
    order_date = request.args.get('order')
    bible_items = []
    orders = load_orders()
    order_data = []
    
    if order_date:
        # Carrega ordem específica por data
        order = orders.get(order_date, {})
        order_data = order.get('itens', [])
    else:
        # Busca a ordem que contém esta música
        song_url = f'/lyrics/{song_id}'
        for date, order in orders.items():
            for item in order.get('itens', []):
                if item.get('url') == song_url:
                    order_date = date
                    order_data = order.get('itens', [])
                    break
            if order_date:
                break
        
        # Se não encontrou, busca a ordem mais próxima (hoje ou futura)
        if not order_date and orders:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            dates = sorted(orders.keys())
            order_date = next((d for d in dates if d >= today), dates[-1] if dates else None)
            order_data = orders.get(order_date, {}).get('itens', [])
        
        # Fallback para sistema antigo
        if not order_data:
            order_file = os.path.join(os.getcwd(), 'order_of_service.json')
            if os.path.exists(order_file):
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_data = json.load(f)
    
    # Extrai itens bíblicos
    for item in order_data:
        if item.get('isBible'):
            reference = item.get('reference', '')
            url = generate_bible_url(reference)
            bible_items.append({
                'reference': reference,
                'url': url
            })

    return render_template('view_song.html', song=song, bible_items=bible_items, order_date=order_date)


# --- Rotas relacionadas às letras ---






@app.route('/lyrics/<int:song_id>')
@login_required
def lyrics(song_id):
    """Exibe as letras de uma música."""
    songs = load_songs()
    song = next((s for s in songs if s['id'] == song_id), None)
    if not song:
        return "Música não encontrada", 404

    # Atualiza o timestamp de last_played
    from datetime import datetime
    song['last_played'] = datetime.now().isoformat()
    save_songs(songs)

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

    return render_template('lyrics.html', song=song, order_date=order_date)

@app.route('/api/lyrics/<int:song_id>')
def api_lyrics(song_id):
    """Retorna os dados completos da música em JSON (para API)."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404
    
    return jsonify(song)

@app.route('/api/lyrics/<int:song_id>/theme', methods=['POST'])
@login_required
def set_song_theme(song_id):
    songs = load_songs()
    song = next((s for s in songs if s['id'] == song_id), None)
    if not song:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    song['theme'] = data.get('theme')  # None limpa o tema
    save_songs(songs)
    return jsonify({'ok': True})

@app.route('/section/<int:song_id>/<int:section_index>')
def section(song_id, section_index):
    """Exibe uma seção específica da música."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
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

@app.route('/lyrics_data/<int:song_id>')
def lyrics_data(song_id):
    """Retorna os dados da primeira seção da música."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404

    section = song['sections'][0]
    return jsonify({
        'title': section['title'],
        'text': section['text'][0]
    })

@app.route('/full-lyrics/<int:song_id>')
def full_lyrics(song_id):
    """Retorna as letras completas da música."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404

    full_lyrics_text = "\n".join([section['text'][0] for section in song['sections']])
    return jsonify({'lyrics': full_lyrics_text})

@app.route('/lyrics/display')
def lyrics_display():
    """Exibe a tela de visualização das letras."""
    # Verifica se há parâmetros de URL para carregar música/seção específica
    song_id = request.args.get('song_id', type=int)
    section_index = request.args.get('section', type=int, default=0)
    
    return render_template('display.html', song_id=song_id, section_index=section_index)

@app.route('/lyrics/display/public')
def lyrics_display_Public():
    """Exibe a tela de visualização das letras para o público."""
    return render_template('display_public.html')

@app.route('/lyrics/display/obs')
def lyrics_display_obs():
    """Overlay transparente para OBS/streaming (Browser Source)."""
    return render_template('display_obs.html')

# Rota para limpar as informações
@app.route('/limpar')
def limpar():
    # Aqui você pode emitir um evento para limpar as informações na tela
    socketio.emit('limpar_tela')
    return 'Informações limpas!', 200

# --- FIM ------ #



# Carregar o JSON das músicas
try:
    with open("songs.json", "r", encoding="utf-8") as f:
        songs = json.load(f)
except FileNotFoundError:
    songs = []


# Função para garantir que o diretório existe e o arquivo será criado
def ensure_file_exists():
    if not os.path.exists('image_paths.json'):
        # Cria o arquivo com uma estrutura inicial se não existir
        with open('image_paths.json', 'w') as f:
            json.dump({"image": None}, f, indent=4)

# Função para carregar o arquivo JSON com o caminho da imagem
def load_image_path():
    ensure_file_exists()  # Verifica se o arquivo existe e cria se necessário
    with open('image_paths.json', 'r') as f:
        return json.load(f)

# Função para salvar o caminho da imagem no arquivo JSON
def save_image_path(image_path):
    # Altera para salvar apenas um caminho
    data = {"image": image_path}
    
    with open('image_paths.json', 'w') as f:
        json.dump(data, f, indent=4)

# Endpoint para salvar o caminho da imagem
@app.route('/save_image_path', methods=['POST'])
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
        bool(__import__('re').search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', url, __import__('re').I))

@app.route('/last_image', methods=['GET'])
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














@app.route('/')
@login_required
def index():
    return redirect(url_for('auth.dashboard'))

@app.route('/control')
@login_required
def control():
    return render_template('control.html')

@app.route('/monitor')
def monitor():
    return render_template('monitor.html')

# Rota para obter o estado atual do display
@app.route('/get_display_state')
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

# Rota para salvar o estado do display
@app.route('/save_display_state', methods=['POST'])
def save_display_state():
    data = request.json
    state = DisplayState.query.first()
    
    if not state:
        state = DisplayState(url1=data.get('url1', ''), url2=data.get('url2', ''))
        db.session.add(state)
    else:
        state.url1 = data.get('url1', '')
        state.url2 = data.get('url2', '')
    
    db.session.commit()
    return jsonify({'status': 'success'})

# Rota para obter o estado atual das letras (música + seção)
@app.route('/get_lyrics_state')
def get_lyrics_state():
    state = LyricsState.query.first()
    if state:
        return jsonify({
            'song_id': state.song_id,
            'section_index': state.section_index
        })
    return jsonify({'song_id': None, 'section_index': 0})

# Rota para salvar o estado das letras (música + seção)
@app.route('/save_lyrics_state', methods=['POST'])
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
    logger.debug(f'💾 Estado das letras salvo: Música {state.song_id}, Seção {state.section_index}')
    return jsonify({'status': 'success'})

# Rota para exibir uma imagem específica
@app.route('/img')
def serve_image():
    image_url = get_current_image_path()
    response = make_response(render_template('img.html', image_url=image_url))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/presenter')
def presenter():
    return render_template('presenter.html')


@socketio.on('video_ended')
def handle_video_ended(data):
    emit('video_ended', {}, broadcast=True)


# Rota para salvar URLs no servidor
@app.route('/save_urls', methods=['POST'])
def save_urls_route():
    urls = request.json
    save_urls(urls)
    return jsonify({'status': 'success'})

# Rota para carregar as URLs salvas
@app.route('/load_urls', methods=['GET'])
def load_urls_route():
    urls = load_urls()
    return jsonify(urls)

# Evento WebSocket para transmitir a URL da imagem
@socketio.on('show_image')
def handle_show_image(data):
    image_url = data['image_url']

    # Imagem substituiu o vídeo no monitor: limpa estado de reprodução
    display_state._video_state['url'] = None
    display_state._video_state['paused'] = False
    display_state._video_state['position_offset'] = 0.0

    # Atualiza modo imediatamente (antes de qualquer retorno antecipado)
    display_state._last_image_url = image_url
    display_state._current_display_mode = 'image'
    logger.debug(f'🖼️ show_image recebido: {image_url} → modo=image')

    # Envia para clientes primeiro (não espera banco)
    emit('display_image', {'image_url': image_url}, broadcast=True, skip_sid=_skip_sids(data))
    append_display_log({'type': 'image', 'title': image_url})

    # Só persiste no banco se for arquivo estático real (não rotas como /img, /lyrics/display)
    is_static_file = image_url.startswith('/static/') or \
        bool(__import__('re').search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', image_url, __import__('re').I))
    if not is_static_file:
        return

    # Mantém cache da última mídia estática
    display_state._last_static_media_url = image_url

    # Atualiza cache
    display_state._display_state_cache['data'] = {'url1': image_url, 'url2': ''}
    display_state._display_state_cache['timestamp'] = time.time()

    # Salva no banco de forma assíncrona
    def save_async():
        with app.app_context():
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

@socketio.on('show_video')
def handle_show_video(data):
    video_url = data.get('video_url')
    logger.debug(f'🎬 [show_video] recebido: {video_url}')
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

    def save_async():
        with app.app_context():
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
    logger.debug(f'⏯️ [toggle_video_pause] paused={paused}')

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
    logger.debug('⏮️ [restart_video] recebido')
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
    logger.debug(f'⏩ [seek_video] time={target:.2f}s')
    if display_state._video_state['url']:
        # Mantém estado de pause: se está pausado, só atualiza o offset; se está
        # tocando, redefine started_at para "agora" com o novo offset.
        display_state._video_state['position_offset'] = target
        display_state._video_state['started_at'] = time.time()
        # paused permanece como está
    emit('video_seek', {'time': target}, broadcast=True)


@app.route('/video_state')
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
    # O botão "Letra" manda o /monitor recarregar '/lyrics/display/public' num
    # iframe. Essa página, ao carregar do zero, busca /api/current-display pra
    # saber o que mostrar — e sem isto aqui, ela mostra o que foi exibido por
    # último de verdade ao público (ex: relógio), não a letra atual.
    # display_state._last_lyrics_payload some a cada restart do servidor, então reconstrói a
    # partir do banco (song_id + section_index), igual ao fallback que
    # /api/current-display já usa quando não há payload em memória.
    if url == '/lyrics/display/public':
        with app.app_context():
            state = LyricsState.query.first()
            if state and state.song_id:
                song = next((s for s in load_songs() if s['id'] == state.song_id), None)
                if song and 0 <= state.section_index < len(song['sections']):
                    section = song['sections'][state.section_index]
                    display_state._last_lyrics_payload = {'title': section['title'], 'text': section['text'][0]}
                    display_state._current_display_mode = 'lyrics'
    for sid in _get_monitor_sids():
        emit('display_monitor_content', {'url': url}, to=sid)

@socketio.on('show_monitor_video')
def handle_show_monitor_video(data):
    """Exibe vídeo apenas no /monitor."""
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
    for sid in _get_monitor_sids():
        emit('display_two_urls', {'url1': data.get('url1', ''), 'url2': data.get('url2', '')}, to=sid)

@app.route('/api/monitor/sync', methods=['POST'])
def api_monitor_sync():
    """Sincroniza o /monitor com o estado público atual (vídeo ou display)."""
    sids = _get_monitor_sids()
    if display_state._video_state['url']:
        pos = display_state._video_current_position()
        for sid in sids:
            socketio.emit('display_monitor_video', {'video_url': display_state._video_state['url']}, to=sid)
            socketio.emit('video_seek', {'time': pos}, to=sid)
            if display_state._video_state['paused']:
                socketio.emit('video_pause', {'paused': True}, to=sid)
    elif display_state._display_state_cache.get('data'):
        state = display_state._display_state_cache['data']
        url = state.get('url1', '')
        if url:
            for sid in sids:
                socketio.emit('display_monitor_content', {'url': url}, to=sid)
    return jsonify({'status': 'ok'})


@socketio.on('blackout')
def handle_blackout(data):
    """Escurece ou restaura a tela de exibição"""
    emit('blackout', {'active': data.get('active', True)}, broadcast=True)

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
        logger.debug(f"[show_image_zoom] url={image_url} zoom={zoom} origin={origin} pan={pan}")
    except Exception:
        pass
    if not image_url:
        return
    emit('display_image_zoom', {'image_url': image_url, 'zoom': zoom, 'origin': origin, 'pan': pan}, broadcast=True)

# Evento WebSocket para transmitir duas URLs de imagem
@socketio.on('show_two_urls')
def handle_show_two_urls(data):

    url1 = data['url1'] or ''
    url2 = data['url2'] or ''

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

    # Para salvar no banco, substitui '/img' pela URL real da última imagem salva
    def _resolve_img_url(u):
        if u != '/img':
            return u
        cached = display_state._display_state_cache.get('data') or {}
        if cached.get('url1') and cached['url1'] != '/img':
            return cached['url1']
        try:
            with app.app_context():
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
        with app.app_context():
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

# Evento WebSocket para transmitir letras de músicas
@socketio.on('update_lyrics')
def handle_update_lyrics(data):
    logger.debug(f'📨 Recebido update_lyrics: {data.get("title", "Sem título")}')
    display_state._last_lyrics_payload = data
    display_state._current_display_mode = 'lyrics'
    emit('update_lyrics', data, broadcast=True)

@app.route('/api/current-display')
def api_current_display():
    if display_state._current_display_mode == 'image' and display_state._last_image_url:
        is_static = display_state._last_image_url.startswith('/static/') or \
            bool(__import__('re').search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', display_state._last_image_url, __import__('re').I))
        return jsonify({'mode': 'image', 'image_url': display_state._last_image_url, 'is_static': is_static})
    if display_state._current_display_mode == 'video' and display_state._last_static_media_url:
        return jsonify({'mode': 'video', 'video_url': display_state._last_static_media_url})
    if display_state._current_display_mode == 'lyrics' and display_state._last_lyrics_payload:
        return jsonify({'mode': 'lyrics', **display_state._last_lyrics_payload})
    # Fallback: busca do banco (song_id + section_index salvos pelo operador)
    state = LyricsState.query.first()
    if state and state.song_id:
        song = next((s for s in load_songs() if s['id'] == state.song_id), None)
        if song and state.section_index < len(song['sections']):
            section = song['sections'][state.section_index]
            return jsonify({
                'mode': 'lyrics',
                'title': section['title'],
                'text': section['text'][0],
                'type': 'text',
                'theme': None
            })
    return jsonify({'mode': 'blank'})

@socketio.on('set_display_bg')
def handle_set_display_bg(data):
    dark = data.get('dark', True)
    settings = load_settings()
    settings['display_bg_dark'] = dark
    save_settings(settings)
    emit('set_display_bg', data, broadcast=True)

@app.route('/api/display-bg')
def get_display_bg():
    settings = load_settings()
    return jsonify({'dark': settings.get('display_bg_dark', True)})

# Evento WebSocket para mudança de seção
@socketio.on('section_changed')
def handle_section_changed(data):
    song_id = data.get('songId')
    logger.debug(f'📨 Recebido section_changed: Song {song_id}, Section {data.get("sectionIndex")}')
    song = next((s for s in load_songs() if s.get('id') == song_id), None)
    song_title = song['title'] if song else str(song_id)
    append_display_log({'type': 'song', 'title': song_title, 'url': f'/lyrics/{song_id}'})
    emit('section_changed', data, broadcast=True)

# Evento WebSocket para mostrar/esconder letras
@socketio.on('toggle_lyrics_visibility')
def handle_toggle_lyrics_visibility(data):
    visible = data.get('visible', True)
    logger.debug(f'👁️ Toggle letras: {"Mostrar" if visible else "Esconder"}')
    emit('lyrics_visibility_changed', {'visible': visible}, broadcast=True)


# === Registro mDNS ===
def registrar_mdns():
    ip_str = obter_endereco_ip().split(":")[0]  # remove a porta
    ip_bytes = socket.inet_aton(ip_str)
    
    info = ServiceInfo(
        "_http._tcp.local.",
        "ucontrol._http._tcp.local.",
        addresses=[ip_bytes],
        port=PORTA,
        properties={},
        server="ucontrol.local.",
    )

    Zeroconf().register_service(info)
    logger.info(f"🔗 Serviço mDNS registrado: http://ucontrol.local:{PORTA}")



# === Abrir navegador ===
def open_browser():
    time.sleep(3)  # Dá tempo do servidor iniciar
    webbrowser.open(f"http://127.0.0.1:{PORTA}/")


# === Execução principal ===
if __name__ == '__main__':
    logger.info(f"✅ Acesse localmente: http://127.0.0.1:{PORTA}/")
    logger.info(f"🌐 Ou via mDNS: http://{MDNS_DOMINIO}:{PORTA}/")
    
    if not os.getenv("UCONTROL_NO_BROWSER"):
        threading.Timer(2, open_browser).start()
    
    debug_enabled = os.getenv("UCONTROL_DEBUG", "0") == "1"
 
    try:
        socketio.run(
            app,
            host="0.0.0.0",
            port=PORTA,
            debug=debug_enabled,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        logger.info("\n🛑 Servidor interrompido pelo usuário")
    except Exception as e:
        logger.exception(f"❌ Erro no servidor: {e}")