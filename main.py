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
from PIL import Image
from datetime import datetime, date
import os
import json
import re
import threading
import requests
import time
import webbrowser
from pychord import Chord
import fitz  # PyMuPDF
from pptx import Presentation
import socket
import qrcode
from bs4 import BeautifulSoup
from zeroconf import ServiceInfo, Zeroconf
import logging
from logging.handlers import RotatingFileHandler

from extensions import db, migrate, login_manager, socketio
from models import User, DisplayState, LyricsState
from display_log import DISPLAY_LOG_PATH, load_display_log, append_display_log
from settings_store import load_settings, save_settings
from blueprints.countdown import countdown_bp
from blueprints.ticker import ticker_bp
from blueprints.auth import auth_bp
from blueprints.bible import bible_bp, generate_bible_url
from blueprints.cifras import cifras_bp
from songs_store import load_songs, save_songs, get_next_id

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


socketio_clients_connected = 0
socketio_clients_by_sid = {}


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
PORTA = 8585
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

    return app


app = create_app()

# Cache simples em memória para reduzir queries no banco
_display_state_cache = {'data': None, 'timestamp': 0}
_cache_ttl = 5  # Cache válido por 5 segundos

# URL da última imagem/vídeo estático clicado — separado do estado do display
_last_static_media_url = None

# Último payload de update_lyrics recebido (para display_public carregar ao abrir)
_last_lyrics_payload = None

# Modo atual do display: 'lyrics' | 'image' | 'video' | 'blank'
_current_display_mode = 'blank'
_last_image_url = None

# Estado de reprodução de vídeo para sincronização entre clientes /img.
# Quando uma nova janela /img conecta, ela consulta este estado para começar
# o vídeo na mesma posição em que ele está tocando nas outras janelas.
#   url:           URL do vídeo atualmente em reprodução (ou None)
#   started_at:    timestamp Unix de quando o vídeo começou OU foi retomado
#   position_offset: posição (segundos) no vídeo no momento de started_at
#                  (0 quando começa do zero; X quando retoma após pausa)
#   paused:        True se está pausado
_video_state = {
    'url': None,
    'started_at': 0.0,
    'position_offset': 0.0,
    'paused': False,
}

def _video_current_position():
    """Retorna a posição (em segundos) atual do vídeo, ou 0 se nada tocando."""
    if not _video_state['url']:
        return 0.0
    if _video_state['paused']:
        return _video_state['position_offset']
    return _video_state['position_offset'] + (time.time() - _video_state['started_at'])

@app.route('/api/culto/status', methods=['GET'])
@login_required
def api_culto_status():
    today = date.today().isoformat()
    orders = load_orders()
    order = orders.get(today)

    if not order:
        return jsonify({
            'status': 'no_service',
            'date': today,
            'message': 'Nenhum culto agendado para hoje',
            'steps': []
        })

    steps = []
    for item in order.get('itens', []):
        title = (item.get('title') or '').strip()
        title_upper = title.upper()
        step_type = 'item'
        if 'ABERTURA' in title_upper or 'INÍCIO' in title_upper or 'INICIO' in title_upper:
            step_type = 'abertura'
        elif 'LOUVOR' in title_upper or 'MÚSICA' in title_upper or 'MUSICA' in title_upper or 'HINO' in title_upper:
            step_type = 'louvor'
        elif 'MENSAGEM' in title_upper or 'PREGAÇÃO' in title_upper or 'PREGACAO' in title_upper or 'PALAVRA' in title_upper or 'PRELEÇÃO' in title_upper or 'PRELECAO' in title_upper:
            step_type = 'mensagem'
        elif 'OFERTA' in title_upper or 'OFERTAS' in title_upper or 'DÍZIMO' in title_upper or 'DIZIMO' in title_upper:
            step_type = 'oferta'
        elif 'ENCERRAMENTO' in title_upper or 'FINAL' in title_upper or 'BÊNÇÃO' in title_upper or 'BENCAO' in title_upper:
            step_type = 'encerramento'

        steps.append({
            'title': title or 'Item',
            'type': step_type
        })

    return jsonify({
        'status': 'ok',
        'date': today,
        'tipo': order.get('tipo', ''),
        'horario': order.get('horario_culto', ''),
        'dirigente': order.get('dirigente', ''),
        'pregador': order.get('pregador', ''),
        'steps': steps
    })


@app.route('/api/system/status', methods=['GET'])
@login_required
def api_system_status():
    ip_local = None
    try:
        ip_local = obter_endereco_ip()
    except Exception:
        ip_local = None

    public_url = None
    try:
        public_url = request.host_url.rstrip('/')
    except Exception:
        public_url = None

    local_url = None
    if ip_local:
        local_url = f"http://{ip_local}:{PORTA}"

    socketio_by_role = {}
    for info in socketio_clients_by_sid.values():
        role = None
        if isinstance(info, dict):
            role = info.get('role')
        if not role:
            role = 'unknown'
        socketio_by_role[role] = socketio_by_role.get(role, 0) + 1

    cpu_percent = None
    ram_percent = None
    system_stats_error = None
    try:
        import psutil
        cpu_percent = float(psutil.cpu_percent(interval=None))
        ram_percent = float(psutil.virtual_memory().percent)
    except Exception as e:
        system_stats_error = str(e)

    disk_total_gb = None
    disk_free_gb = None
    disk_used_percent = None
    disk_error = None
    try:
        import psutil
        usage = psutil.disk_usage('/')
        disk_total_gb = round(usage.total / (1024 ** 3), 1)
        disk_free_gb = round(usage.free / (1024 ** 3), 1)
        disk_used_percent = float(usage.percent)
    except Exception as e:
        disk_error = str(e)

    payload = {
        'online': True,
        'ip': ip_local,
        'port': PORTA,
        'public_url': public_url,
        'local_url': local_url,
        'socketio_clients': socketio_clients_connected,
        'socketio_by_role': socketio_by_role,
        'cpu_percent': cpu_percent,
        'ram_percent': ram_percent,
        'disk_total_gb': disk_total_gb,
        'disk_free_gb': disk_free_gb,
        'disk_used_percent': disk_used_percent

    }
    if app.debug and system_stats_error:
        payload['system_stats_error'] = system_stats_error
    if app.debug and disk_error:
        payload['disk_error'] = disk_error

    return jsonify(payload)





# QR CODE

def obter_endereco_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_local = s.getsockname()[0]
    s.close()
    return ip_local

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

@app.route("/links")
def exibir_links():
    rotas = [
        ("/", "Controle"),
        ("monitor", "Monitor"),
        ("presenter", "Controle de Imagem"),
        ("order", "Ordem do Culto"),
        ("lyrics/display", "Monitor de Letra"),
        ("img", "Monitor de Imagem"),
        ("songs", "Biblioteca de Músicas"),
        ("bible", "Bíblia"),
        ("bible/display", "Bíblia - Display"),
        ("help", "Ajuda")
    ]
    ip_local = obter_endereco_ip()
    porta_url = f"http://{ip_local}:{PORTA}"
    
    dados = []
    for rota, nome in rotas:
        url = f"{porta_url}/{rota}"
        nome_arquivo = rota.replace("/", "_") + "_qr_code"
        dados.append({
            "url": url,
            "nome": nome,
            "img": f"/static/qrcodes/{nome_arquivo}.png",
            "img_id": nome_arquivo
        })
    
    return render_template("links.html", dados=dados)









# Diretório onde as imagens estão armazenadas
IMAGE_FOLDER = 'static/imagens'
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER

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

# Função para obter o caminho da imagem atual
def get_current_image_path():
    images = os.listdir(app.config['IMAGE_FOLDER'])
    if images:
        return f"/static/imagens/{images[0]}"
    return ""






# --- Rotas principais editor---

@app.route('/songs')
@login_required
def list_songs():
    """Lista todas as músicas."""
    return render_template('list_songs.html', songs=load_songs())

@app.route('/new_song')
@login_required
def new_song():
    """Exibe o formulário para criar uma nova música."""
    return render_template('new_song.html')

@app.route('/sheet_editor')
@login_required
def sheet_editor():
    """Exibe o editor de partitura VexFlow."""
    return render_template('sheet_editor.html')

@app.route('/sheet_editor/<int:song_id>')
@login_required
def edit_sheet(song_id):
    """Edita a partitura de uma música específica."""
    songs = load_songs()
    song = next((s for s in songs if s['id'] == song_id), None)
    if not song:
        flash('Música não encontrada!', 'error')
        return redirect(url_for('list_songs'))
    return render_template('sheet_editor.html', song=song)

@app.route('/api/save_sheet/<int:song_id>', methods=['POST'])
@login_required
def save_sheet_data(song_id):
    """Salva os dados da partitura em uma música."""
    try:
        sheet_data = request.get_json()
        songs = load_songs()
        
        # Encontra a música
        song = next((s for s in songs if s['id'] == song_id), None)
        if not song:
            return jsonify({"error": "Música não encontrada"}), 404
        
        # Salva os dados da partitura
        song['sheet_data'] = sheet_data
        save_songs(songs)
        
        return jsonify({"message": "Partitura salva com sucesso!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_song', methods=['POST'])
def add_song():
    """Adiciona uma nova música."""
    import sys
    sys.stdout.flush()  # Força flush do stdout
    
    logger.debug("🎼 [DEBUG] Iniciando add_song...")
    
    title = request.form['title']
    author = request.form['author']
    sections = request.form.getlist('sections[]')
    texts = request.form.getlist('texts[]')
    
    logger.debug(f"📝 [DEBUG] Título: {title}")
    logger.debug(f"👤 [DEBUG] Autor: {author}")
    logger.debug(f"📄 [DEBUG] Textos: {texts}")
    
    # Captura dados da partitura se enviados
    sheet_data_json = request.form.get('sheet_data')
    logger.debug(f"🎵 [DEBUG] Sheet data recebido: {bool(sheet_data_json)}")
    if sheet_data_json:
        logger.debug(f"📊 [DEBUG] Tamanho dos dados: {len(sheet_data_json)} caracteres")
        logger.debug(f"📋 [DEBUG] Primeiros 200 chars: {sheet_data_json[:200]}...")
    
    # Captura URL do vídeo de referência
    video_url = request.form.get('video_url', '').strip()
    if video_url:
        logger.debug(f"🎬 [DEBUG] Video URL recebido: {video_url}")
    
    # Captura URL do áudio local
    audio_url = request.form.get('audio_url', '').strip()
    if audio_url:
        logger.debug(f"🎵 [DEBUG] Audio URL recebido: {audio_url}")

    songs = load_songs()
    new_song = {
        "id": get_next_id(songs),
        "title": title,
        "author": author,
        "sections": [
            {"title": sections[i], "text": [texts[i]]} for i in range(len(sections))
        ]
    }
    
    # Adiciona URL do vídeo se fornecida
    if video_url:
        new_song["video_url"] = video_url
    
    # Adiciona URL do áudio se fornecida
    if audio_url:
        new_song["audio_url"] = audio_url
    
    logger.debug(f"🆔 [DEBUG] Nova música ID: {new_song['id']}")
    
    # Se há dados de partitura, adiciona ao objeto da música
    if sheet_data_json:
        try:
            import json
            sheet_data = json.loads(sheet_data_json)
            new_song["sheet_data"] = sheet_data
            
            # Verifica se é array (múltiplas partituras) ou objeto (partitura única)
            if isinstance(sheet_data, list):
                total_notes = sum(len(s.get('notes', [])) for s in sheet_data)
                logger.debug(f"✅ [DEBUG] {len(sheet_data)} partitura(s) adicionada(s) com {total_notes} notas no total")
            else:
                logger.debug(f"✅ [DEBUG] Sheet data adicionado com {len(sheet_data.get('notes', []))} notas")
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}")
    
    # Verifica se alguma seção tem marcador de partitura integrada
    for section in new_song["sections"]:
        for i, text in enumerate(section["text"]):
            if "[🎼 PARTITURA_INTEGRADA]" in text:
                logger.debug(f"🔍 [DEBUG] Marcador encontrado no texto: {text}")
                # Se há dados de partitura, substitui o marcador
                if sheet_data_json:
                    try:
                        sheet_data = json.loads(sheet_data_json)
                        new_song["sheet_data"] = sheet_data
                        logger.debug(f"✅ [DEBUG] Dados da partitura processados e salvos")
                        # Remove o marcador do texto
                        section["text"][i] = text.replace("[🎼 PARTITURA_INTEGRADA]", "").strip()
                        # Remove linhas vazias resultantes
                        section["text"] = [t for t in section["text"] if t.strip()]
                        logger.debug(f"🧹 [DEBUG] Marcador removido do texto")
                    except Exception as e:
                        logger.debug(f"❌ [DEBUG] Erro ao processar marcador: {e}")
                break
    
    logger.debug(f"💾 [DEBUG] Salvando música com sheet_data: {bool(new_song.get('sheet_data'))}")
    if new_song.get('sheet_data'):
        sheet_data = new_song['sheet_data']
        if isinstance(sheet_data, list):
            total_notes = sum(len(s.get('notes', [])) for s in sheet_data)
            logger.debug(f"📊 [DEBUG] {len(sheet_data)} partitura(s) na música final com {total_notes} notas no total")
        else:
            logger.debug(f"📊 [DEBUG] Notas na música final: {len(sheet_data.get('notes', []))}")
    
    songs.append(new_song)
    save_songs(songs)
    
    logger.debug(f"✅ [DEBUG] Música salva com sucesso!")
    return jsonify({"message": "Música adicionada com sucesso!"})

@app.route('/edit_song/<int:song_id>', methods=['GET', 'POST'])
def edit_song(song_id):
    """Edita uma música existente."""
    songs = load_songs()

    if request.method == 'POST':
        # Usa a mesma lógica do add_song
        title = request.form['title']
        author = request.form['author']
        sections = request.form.getlist('sections[]')
        texts = request.form.getlist('texts[]')
        sheet_data_json = request.form.get('sheet_data')
        video_url = request.form.get('video_url', '').strip()
        audio_url = request.form.get('audio_url', '').strip()
        
        logger.debug(f"🔄 [DEBUG] Editando música ID: {song_id}")
        if video_url:
            logger.debug(f"🎬 [DEBUG] Video URL: {video_url}")
        if audio_url:
            logger.debug(f"🎵 [DEBUG] Audio URL: {audio_url}")
        logger.debug(f"📝 [DEBUG] Título: {title}")
        logger.debug(f"👤 [DEBUG] Autor: {author}")
        logger.debug(f"📋 [DEBUG] Seções recebidas: {len(sections)}")
        logger.debug(f"📄 [DEBUG] Textos recebidos: {len(texts)}")
        # DEBUG: Mostra espaços no primeiro texto
        if texts:
            logger.debug(f"🔍 [DEBUG] Primeiro texto (repr): {repr(texts[0])}")
            logger.debug(f"🔍 [DEBUG] Espaços no primeiro texto: {texts[0].count(' ')}")
            logger.debug(f"🔍 [DEBUG] Primeiros 100 chars: {repr(texts[0][:100])}")
            logger.debug(f"🔍 [DEBUG] Começa com espaço? {texts[0].startswith(' ')}")
        
        # Encontra a música existente
        song_to_update = None
        for song in songs:
            if song['id'] == song_id:
                song_to_update = song
                break
        
        if not song_to_update:
            return jsonify({"error": "Música não encontrada!"}), 404
        
        # Atualiza os dados
        song_to_update.update({
            "title": title,
            "author": author,
            "sections": [
                {"title": sections[i], "text": [texts[i]]} for i in range(len(sections))
            ]
        })
        
        # Se há dados de partitura, adiciona/atualiza
        if sheet_data_json:
            try:
                import json
                sheet_data = json.loads(sheet_data_json)
                song_to_update["sheet_data"] = sheet_data
                
                # Verifica se é array (múltiplas partituras) ou objeto (partitura única)
                if isinstance(sheet_data, list):
                    total_notes = sum(len(s.get('notes', [])) for s in sheet_data)
                    logger.debug(f"✅ [DEBUG] {len(sheet_data)} partitura(s) atualizada(s) com {total_notes} notas no total")
                else:
                    logger.debug(f"✅ [DEBUG] Partitura atualizada com {len(sheet_data.get('notes', []))} notas")
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}")
        
        # Atualiza URL do vídeo
        if video_url:
            song_to_update["video_url"] = video_url
        elif "video_url" in song_to_update and not video_url:
            # Remove se estava preenchido e agora está vazio
            del song_to_update["video_url"]
        
        # Atualiza URL do áudio
        if audio_url:
            song_to_update["audio_url"] = audio_url
        elif "audio_url" in song_to_update and not audio_url:
            # Remove se estava preenchido e agora está vazio
            del song_to_update["audio_url"]
        
        save_songs(songs)
        logger.debug(f"✅ [DEBUG] Música {song_id} editada com sucesso!")
        return jsonify({"message": "Música editada com sucesso!"})

    song_to_edit = next((song for song in songs if song['id'] == song_id), None)
    return render_template('edit_song.html', song=song_to_edit)

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


@app.route('/delete_song/<int:song_id>', methods=['POST'])
def delete_song(song_id):
    """Exclui uma música."""
    songs = load_songs()
    songs = [s for s in songs if s['id'] != song_id]
    save_songs(songs)

    return jsonify({'message': 'Música removida com sucesso!'})

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

@app.route('/save_route', methods=['POST'])
def save_route():
    data = request.get_json()  # Obtém os dados JSON enviados
    new_url = data.get('url1')  # Obtém a nova URL do JSON

    # Lê o conteúdo existente do arquivo urls.json
    with open('urls.json', 'r+') as file:
        urls = json.load(file)  # Carrega o conteúdo existente
        urls['url1'] = new_url  # Atualiza o valor de url1
        file.seek(0)  # Volta para o início do arquivo
        json.dump(urls, file, indent=4)  # Salva as URLs atualizadas
        file.truncate()  # Remove o restante do arquivo, se houver

    return jsonify(status='success')  # Retorna uma resposta de sucesso

# Rota para limpar as informações
@app.route('/limpar')
def limpar():
    # Aqui você pode emitir um evento para limpar as informações na tela
    socketio.emit('limpar_tela')
    return 'Informações limpas!', 200

# Evento para quando o cliente se conectar
@socketio.on('connect')
def handle_connect():
    global socketio_clients_connected
    sid = request.sid
    socketio_clients_by_sid[sid] = socketio_clients_by_sid.get(sid) or {'role': 'unknown'}
    socketio_clients_connected = len(socketio_clients_by_sid)
    logger.info('Cliente conectado')


@socketio.on('disconnect')
def handle_disconnect():
    global socketio_clients_connected
    sid = request.sid
    if sid in socketio_clients_by_sid:
        del socketio_clients_by_sid[sid]
    socketio_clients_connected = len(socketio_clients_by_sid)
    logger.info('Cliente desconectado')


@socketio.on('identify')
def handle_identify(data):
    sid = request.sid
    role = None
    if isinstance(data, dict):
        role = data.get('role')
    if not role:
        role = 'unknown'
    if sid not in socketio_clients_by_sid:
        socketio_clients_by_sid[sid] = {'role': role}
    else:
        socketio_clients_by_sid[sid]['role'] = role
    if role in ('public', 'monitor'):
        join_room(role)




# --- FIM ------ #



# Load the order of service from the JSON file
DATA_FILE = 'order_of_service.json'
ORDERS_FILE = 'orders.json'
TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'order_templates.json')

def load_templates():
    try:
        if os.path.exists(TEMPLATES_FILE):
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def save_templates_file(templates):
    try:
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

# Funções auxiliares para o novo sistema de ordens
def load_orders():
    """Carrega todas as ordens do arquivo orders.json"""
    try:
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.exception(f"Erro ao carregar orders.json: {e}")
        return {}

def save_orders(orders):
    """Salva todas as ordens no arquivo orders.json"""
    try:
        with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.exception(f"Erro ao salvar orders.json: {e}")
        return False

# API para listar todas as ordens
@app.route('/api/orders', methods=['GET'])
def api_get_orders():
    """Retorna todas as ordens de culto"""
    orders = load_orders()
    return jsonify(orders)

# API para obter uma ordem específica
@app.route('/api/orders/<date>', methods=['GET'])
def api_get_order(date):
    """Retorna uma ordem específica por data"""
    orders = load_orders()
    if date in orders:
        return jsonify(orders[date])
    return jsonify({"error": "Ordem não encontrada"}), 404

# API para salvar/atualizar uma ordem
@app.route('/api/orders/<date>', methods=['POST'])
@login_required
def api_save_order(date):
    """Salva ou atualiza uma ordem específica"""
    try:
        data = request.get_json(force=True) or {}
        orders = load_orders()

        order = orders.get(date, {})

        # ---------- EVENTOS -----------
        eventos = data.get('eventos', [])
        lista_eventos = []

        if isinstance(eventos, list):
            lista_eventos = [
                {
                    'titulo': e.get('titulo', '').strip(),
                    'hora': e.get('hora', '').strip(),
                    'responsavel': e.get('responsavel', '').strip(),
                    'obs': e.get('obs', '').strip()
                }
                for e in eventos
                if (e.get('titulo') or '').strip()
            ]
        # só salva se tiver conteúdo
        if lista_eventos:
            order['eventos'] = lista_eventos
        else:
            order.pop('eventos', None)

        # ---------- LOUVOR ----------
        tipo = (data.get('tipo') or '').strip()
        horario = (data.get('horario_culto') or '').strip()
        dirigente = (data.get('dirigente') or '').strip()
        pregador = (data.get('pregador') or '').strip()

        louvor = data.get('louvor') or {}
        cantores = louvor.get('cantores') or []
        musicos = louvor.get('musicos') or []

        itens = data.get('itens') or []

        tem_louvor = (
            (tipo and tipo.lower() != 'nenhum') or
            horario or
            dirigente or
            pregador or
            len(cantores) > 0 or
            len(musicos) > 0 or
            len(itens) > 0
        )

        if tem_louvor:
            order['tipo'] = tipo
            order['horario_culto'] = horario
            order['dirigente'] = dirigente
            order['pregador'] = pregador
            order['louvor'] = {
                'cantores': cantores,
                'musicos': musicos
            }
            order['itens'] = itens
        else:
            order.pop('tipo', None)
            order.pop('horario_culto', None)
            order.pop('dirigente', None)
            order.pop('pregador', None)
            order.pop('louvor', None)
            order.pop('itens', None)

        # ---------- MÍDIA ----------
        midia = data.get('midia') or {}

        lider = (midia.get('lider') or '').strip()
        palco = (midia.get('palco') or '').strip()
        visual = (midia.get('visual') or '').strip()
        equipe = midia.get('equipe') or []
        obs = (midia.get('obs') or '').strip()

        tem_midia = (
            lider or palco or visual or obs or len(equipe) > 0
        )

        if tem_midia:
            order['midia'] = {
                'lider': lider,
                'palco': palco,
                'visual': visual,
                'equipe': equipe,
                'obs': obs
            }
        else:
            order.pop('midia', None)

        # ---------- LIMPEZA AUTOMÁTICA ----------
        def is_empty_order(o):
            return len(o) == 0

        if is_empty_order(order):
            # remove do banco se estiver vazio
            if date in orders:
                del orders[date]
        else:
            # salva normalmente
            orders[date] = order

        if save_orders(orders):
            return jsonify({"message": "Ordem salva com sucesso!"}), 200

        return jsonify({"error": "Erro ao salvar ordem"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API para deletar uma ordem
@app.route('/api/orders/<date>', methods=['DELETE'])
@login_required
def api_delete_order(date):
    """Deleta uma ordem específica"""
    try:
        orders = load_orders()
        if date in orders:
            del orders[date]
            if save_orders(orders):
                return jsonify({"message": "Ordem deletada com sucesso!"}), 200
        return jsonify({"error": "Ordem não encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/templates', methods=['GET'])
def api_get_templates():
    return jsonify(load_templates())

@app.route('/api/templates', methods=['POST'])
@login_required
def api_save_template():
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    items = data.get('items', [])
    if not name:
        return jsonify({'error': 'Nome obrigatório'}), 400
    templates = load_templates()
    templates[name] = items
    save_templates_file(templates)
    return jsonify({'ok': True})

@app.route('/api/templates/<path:name>', methods=['DELETE'])
@login_required
def api_delete_template(name):
    templates = load_templates()
    templates.pop(name, None)
    save_templates_file(templates)
    return jsonify({'ok': True})

SECTION_TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'section_templates.json')

def load_section_templates():
    try:
        if os.path.exists(SECTION_TEMPLATES_FILE):
            with open(SECTION_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def save_section_templates(data):
    try:
        with open(SECTION_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

@app.route('/api/section-templates/<section>', methods=['GET'])
def api_get_section_templates(section):
    return jsonify(load_section_templates().get(section, {}))

@app.route('/api/section-templates/<section>', methods=['POST'])
@login_required
def api_save_section_template(section):
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    fields = data.get('fields', {})
    if not name:
        return jsonify({'error': 'Nome obrigatório'}), 400
    all_tpls = load_section_templates()
    all_tpls.setdefault(section, {})[name] = fields
    save_section_templates(all_tpls)
    return jsonify({'ok': True})

@app.route('/api/section-templates/<section>/<path:name>', methods=['DELETE'])
@login_required
def api_delete_section_template(section, name):
    all_tpls = load_section_templates()
    all_tpls.get(section, {}).pop(name, None)
    save_section_templates(all_tpls)
    return jsonify({'ok': True})

@app.route('/api/section-templates/apply-month', methods=['POST'])
@login_required
def api_apply_section_template_month():
    data = request.get_json(force=True) or {}
    section = data.get('section', '').strip()
    fields = data.get('fields', {})
    dates = data.get('dates', [])
    if not section or not fields or not dates:
        return jsonify({'error': 'Parâmetros obrigatórios: section, fields, dates'}), 400
    orders = load_orders()
    for d in dates:
        order = orders.get(d, {})
        if section == 'louvor':
            # dirigente/pregador/tipo vivem na raiz do order, não dentro de order["louvor"]
            for key in ('dirigente', 'pregador', 'tipo', 'horario_culto'):
                if key in fields:
                    order[key] = fields[key]
            if 'louvor' in fields:
                order['louvor'] = fields['louvor']
        else:
            order[section] = fields
        orders[d] = order
    save_orders(orders)
    return jsonify({'ok': True, 'applied': len(dates)})

# Rota para salvar a lista (mantém compatibilidade com sistema antigo)
@app.route('/save', methods=['POST'])
def save_list():
    try:
        data = request.json
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return jsonify({"message": "Lista salva com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para carregar a lista (mantém compatibilidade com sistema antigo)
@app.route('/load', methods=['GET'])
def load_list():
    try:
        # Verifica se há parâmetro de data
        date = request.args.get('date')
        if date:
            orders = load_orders()
            if date in orders:
                return jsonify(orders[date].get('itens', [])), 200
            return jsonify([]), 200
        
        # Fallback para sistema antigo
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Carregar o JSON das músicas
try:
    with open("songs.json", "r", encoding="utf-8") as f:
        songs = json.load(f)
except FileNotFoundError:
    songs = []

# Rota principal - Lista de ordens
@app.route("/order")
@login_required
def order_list():
    """Lista todas as ordens de culto em cards"""
    return render_template("order_list.html")

# Rota para criar nova ordem
@app.route("/order/new")
@login_required
def order_new():
    """Página para criar nova ordem de culto"""
    # Gera data de hoje como padrão
    from datetime import date
    today = date.today().isoformat()
    return render_template("order_edit.html", date=today, order=None, is_new=True)

# Rota para editar ordem existente
@app.route("/order/<date>")
@login_required
def order_edit(date):
    """Página para editar ordem de culto existente"""
    orders = load_orders()
    order = orders.get(date)
    return render_template("order_edit.html", date=date, order=order, is_new=False)

# Agenda com calendário e detalhes por data
@app.route("/agenda/hoje")
def agenda_hoje():
    """Redireciona para o próximo culto cadastrado (hoje ou futuro)."""
    from datetime import date as _date, timedelta
    orders = load_orders()
    today = _date.today()
    # Procura até 30 dias à frente
    for i in range(30):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        if d in orders and orders[d]:
            return redirect(url_for("agenda_detail", date=d))
    # Nenhum culto cadastrado nos próximos 30 dias
    return render_template("agenda_hoje_vazio.html"), 200


@app.route("/agenda")
def agenda_calendar():
    """Calendário de escalas por data"""
    return render_template("agenda_calendar.html")


@app.route("/agenda/edit", methods=["GET"])
@login_required
def agenda_edit_selector():
    """Calendário privado para escolher a data e editar a agenda/ordem"""
    return render_template("agenda_calendar_edit.html")


@app.route("/agenda/dashboard")
@login_required
def agenda_dashboard():
    """Painel privado de acesso rápido à Agenda de Equipes"""
    return render_template("agenda_dashboard.html")


@app.route("/agenda/<dateslug:date>")
def agenda_detail(date):
    """Detalhe da agenda de uma data específica"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_detail.html", date=date, order=order, allow_clicks=False)


@app.route("/agenda/<dateslug:date>/louvor")
def agenda_louvor(date):
    """Página específica para Louvor e Dirigência"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="louvor")


@app.route("/agenda/<dateslug:date>/midia")
def agenda_midia(date):
    """Página específica para Escala de Mídia"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="midia")


@app.route("/agenda/<dateslug:date>/eventos")
def agenda_eventos(date):
    """Página específica para Eventos"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="eventos")


@app.route("/agenda/<dateslug:date>/edit")
@login_required
def agenda_edit(date):
    """Rota privada para editar a agenda/ordem de uma data (mesmo form de /order/<date>)"""
    orders = load_orders()
    order = orders.get(date)
    return render_template("order_edit.html", date=date, order=order, is_new=False)


@app.route("/agenda/<dateslug:date>/admin")
@login_required
def agenda_detail_admin(date):
    """Detalhe da agenda para administradores, com cards clicáveis"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_detail.html", date=date, order=order, allow_clicks=True)

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify([])  # Retorna lista vazia se não houver consulta

    # Carregar as músicas do arquivo sempre que a pesquisa for feita
    songs = load_songs()  # Carrega as músicas do arquivo

    results = []
    for song in songs:
        # Verificar se o título ou autor contém a consulta
        if query in song["title"].lower() or query in song["author"].lower():
            if song not in results:  # Evita duplicatas
                results.append(song)
            continue

        # Verificar se a letra contém a consulta
        for section in song["sections"]:
            for line in section["text"]:
                if query in line.lower():
                    if song not in results:  # Evita duplicatas
                        results.append(song)
                    break

    return jsonify(results)





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
    global _last_static_media_url
    # 1. Usa cache em memória (mais recente)
    if _last_static_media_url:
        ext = _last_static_media_url.lower().split('?')[0]
        media_type = 'video' if ext.endswith(('.mp4', '.webm', '.mov')) else 'image'
        return jsonify({'image_url': _last_static_media_url, 'media_type': media_type}), 200
    # 2. Fallback: busca no banco — procura a primeira URL estática em url1 ou url2
    state = DisplayState.query.first()
    if state:
        for url in [state.url1, state.url2]:
            if _is_static_media(url):
                ext = (url or '').lower().split('?')[0]
                media_type = 'video' if ext.endswith(('.mp4', '.webm', '.mov')) else 'image'
                _last_static_media_url = url
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
    global _display_state_cache
    import time as time_module
    
    # Verifica se o cache ainda é válido
    current_time = time_module.time()
    if _display_state_cache['data'] and (current_time - _display_state_cache['timestamp']) < _cache_ttl:
        return jsonify(_display_state_cache['data'])
    
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
    _display_state_cache['data'] = result
    _display_state_cache['timestamp'] = current_time
    
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

# Rota para listar pastas de imagens
@app.route('/api/image_folders')
def list_image_folders():
    base = app.config['IMAGE_FOLDER']
    folders = ['Geral']  # pasta raiz sempre existe
    if os.path.exists(base):
        for name in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, name)):
                folders.append(name)
    return jsonify(folders)

# Rota para criar pasta
@app.route('/api/image_folders', methods=['POST'])
@login_required
def create_image_folder():
    name = (request.json.get('name') or '').strip()
    if not name or name == 'Geral' or '/' in name or '\\' in name or '..' in name:
        return jsonify({'status': 'error', 'message': 'Nome inválido.'}), 400
    folder_path = os.path.join(app.config['IMAGE_FOLDER'], name)
    if os.path.exists(folder_path):
        return jsonify({'status': 'error', 'message': 'Pasta já existe.'}), 400
    os.mkdir(folder_path)
    return jsonify({'status': 'success', 'name': name})

# Rota para deletar pasta
@app.route('/api/image_folders/<name>', methods=['DELETE'])
@login_required
def delete_image_folder(name):
    if name == 'Geral':
        return jsonify({'status': 'error', 'message': 'Não é possível excluir a pasta Geral.'}), 400
    folder_path = os.path.join(app.config['IMAGE_FOLDER'], name)
    if not os.path.exists(folder_path):
        return jsonify({'status': 'error', 'message': 'Pasta não encontrada.'}), 404
    import shutil
    shutil.rmtree(folder_path)
    return jsonify({'status': 'success'})

# Rota para listar as imagens (suporta ?folder=nome)
@app.route('/imagens')
def list_images():
    folder = request.args.get('folder', 'Geral')
    base = app.config['IMAGE_FOLDER']
    if folder == 'Geral':
        target = base
        prefix = '/static/imagens'
    else:
        target = os.path.join(base, folder)
        prefix = f'/static/imagens/{folder}'
    if not os.path.exists(target):
        return jsonify([])
    images = [f for f in os.listdir(target) if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and os.path.isfile(os.path.join(target, f))]
    image_urls = [f'{prefix}/{image}' for image in images]
    return jsonify(image_urls)

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


@app.route('/download-monitor-launcher/<so>')
def download_monitor_launcher(so):
    """
    Gera um script de inicialização do monitor (/img) já com o IP/porta
    do servidor preenchidos. Abre o Chrome com autoplay liberado para que
    vídeos toquem com som automaticamente.
    Suporta: windows (.bat), linux (.sh), mac (.command)
    """
    server_host = request.host  # ex: 192.168.1.10:8585
    url = f'http://{server_host}/img'

    so = (so or '').lower()

    if so == 'windows':
        content = (
            '@echo off\r\n'
            'REM ============================================================\r\n'
            'REM  U-Control - Iniciar Monitor (Telao)\r\n'
            'REM  Abre o Chrome em modo app, com autoplay liberado (audio+video)\r\n'
            'REM ============================================================\r\n'
            '\r\n'
            f'set URL={url}\r\n'
            '\r\n'
            'set BROWSER=\r\n'
            'REM Tenta Google Chrome\r\n'
            'if exist "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'if exist "%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'if exist "%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe" set BROWSER=%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe\r\n'
            'REM Fallback: Microsoft Edge (Chromium, aceita as mesmas flags)\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe" set BROWSER=%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe" set BROWSER=%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe\r\n'
            'REM Fallback: Brave\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" set BROWSER=%ProgramFiles%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe\r\n'
            'if "%BROWSER%"=="" if exist "%ProgramFiles(x86)%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" set BROWSER=%ProgramFiles(x86)%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe\r\n'
            '\r\n'
            'if "%BROWSER%"=="" (\r\n'
            '    echo.\r\n'
            '    echo ==========================================================\r\n'
            '    echo  Nenhum navegador compativel encontrado.\r\n'
            '    echo  Instale um dos seguintes:\r\n'
            '    echo    - Google Chrome:   https://www.google.com/chrome/\r\n'
            '    echo    - Microsoft Edge:  https://www.microsoft.com/edge\r\n'
            '    echo    - Brave Browser:   https://brave.com/\r\n'
            '    echo ==========================================================\r\n'
            '    pause\r\n'
            '    exit /b 1\r\n'
            ')\r\n'
            '\r\n'
            'set PROFILE_DIR=%LocalAppData%\\UControl-Monitor\r\n'
            'start "" "%BROWSER%" --autoplay-policy=no-user-gesture-required --user-data-dir="%PROFILE_DIR%" --no-first-run --no-default-browser-check --app=%URL% --start-fullscreen\r\n'
        )
        filename = 'Iniciar-Monitor-UControl.bat'
        mimetype = 'application/octet-stream'

    elif so == 'linux':
        content = (
            '#!/bin/bash\n'
            '# ============================================================\n'
            '#  U-Control - Iniciar Monitor (Telao)\n'
            '#  Abre o Chrome em modo app, com autoplay liberado (audio+video)\n'
            '# ============================================================\n'
            '\n'
            f'URL="{url}"\n'
            '\n'
            'CHROME=""\n'
            'for c in google-chrome google-chrome-stable chromium chromium-browser brave-browser microsoft-edge microsoft-edge-stable; do\n'
            '    if command -v "$c" >/dev/null 2>&1; then\n'
            '        CHROME="$c"\n'
            '        break\n'
            '    fi\n'
            'done\n'
            '\n'
            'if [ -z "$CHROME" ]; then\n'
            '    echo ""\n'
            '    echo "=========================================================="\n'
            '    echo " Nenhum navegador compativel encontrado."\n'
            '    echo " Instale um dos seguintes:"\n'
            '    echo "   - Google Chrome:   https://www.google.com/chrome/"\n'
            '    echo "   - Chromium:        sudo apt install chromium-browser"\n'
            '    echo "   - Microsoft Edge:  https://www.microsoft.com/edge"\n'
            '    echo "   - Brave Browser:   https://brave.com/"\n'
            '    echo "=========================================================="\n'
            '    read -p "Pressione Enter para sair..."\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'PROFILE_DIR="$HOME/.config/ucontrol-monitor"\n'
            'mkdir -p "$PROFILE_DIR"\n'
            '"$CHROME" --autoplay-policy=no-user-gesture-required --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check --app="$URL" --start-fullscreen &\n'
        )
        filename = 'Iniciar-Monitor-UControl.sh'
        mimetype = 'application/x-sh'

    elif so in ('mac', 'macos', 'osx'):
        content = (
            '#!/bin/bash\n'
            '# ============================================================\n'
            '#  U-Control - Iniciar Monitor (Telao)\n'
            '#  Abre o Chrome em modo app, com autoplay liberado (audio+video)\n'
            '# ============================================================\n'
            '\n'
            f'URL="{url}"\n'
            '\n'
            'CHROME=""\n'
            'for c in \\\n'
            '    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\\n'
            '    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \\\n'
            '    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \\\n'
            '    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do\n'
            '    if [ -f "$c" ]; then\n'
            '        CHROME="$c"\n'
            '        break\n'
            '    fi\n'
            'done\n'
            '\n'
            'if [ -z "$CHROME" ]; then\n'
            '    echo ""\n'
            '    echo "=========================================================="\n'
            '    echo " Nenhum navegador compativel encontrado em /Applications."\n'
            '    echo " Instale um dos seguintes:"\n'
            '    echo "   - Google Chrome:   https://www.google.com/chrome/"\n'
            '    echo "   - Microsoft Edge:  https://www.microsoft.com/edge"\n'
            '    echo "   - Brave Browser:   https://brave.com/"\n'
            '    echo "=========================================================="\n'
            '    read -p "Pressione Enter para sair..."\n'
            '    exit 1\n'
            'fi\n'
            '\n'
            'PROFILE_DIR="$HOME/Library/Application Support/UControl-Monitor"\n'
            'mkdir -p "$PROFILE_DIR"\n'
            '"$CHROME" --autoplay-policy=no-user-gesture-required --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check --app="$URL" --start-fullscreen &\n'
        )
        filename = 'Iniciar-Monitor-UControl.command'
        mimetype = 'application/x-sh'

    else:
        return jsonify({'error': 'Sistema operacional inválido. Use: windows, linux ou mac.'}), 400

    response = make_response(content)
    response.headers['Content-Type'] = mimetype
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@app.route('/help')
def help():
    return render_template('help.html')

@app.route("/clock", methods=["GET", "POST"])
def clock():
    if request.method == "POST":
        # Handle form data here if needed
        pass

    return render_template("relogio.html")

@socketio.on('video_ended')
def handle_video_ended(data):
    emit('video_ended', {}, broadcast=True)

@app.route('/foto-atual')
def foto_atual():
    return jsonify({'foto_atual': get_current_image_path()})

def obter_proxima_foto():
    global indice_foto_atual
    if len(fotos) == 0:
        return None  # Retorna None se não houver fotos
    indice_foto_atual = (indice_foto_atual + 1) % len(fotos)  # Incrementa e faz um loop no índice
    return fotos[indice_foto_atual]  # Retorna a nova foto

@socketio.on('proxima_foto')
def handle_proxima_foto():
    # Lógica para alterar a foto atual para a próxima foto
    nova_foto = obter_proxima_foto()  # Função para obter o caminho da próxima foto
    emit('atualizar_foto', {'foto_atual': nova_foto}, broadcast=True)

@socketio.on('anterior_foto')
def handle_anterior_foto():
    # Lógica para alterar a foto atual para a foto anterior
    nova_foto = obter_foto_anterior()  # Função para obter o caminho da foto anterior
    emit('atualizar_foto', {'foto_atual': nova_foto}, broadcast=True)

@app.route('/lista-fotos')
def lista_fotos():
    folder = request.args.get('folder', 'Geral')
    base = IMAGE_FOLDER
    if folder == 'Geral':
        target = base
        prefix = '/static/imagens'
    else:
        target = os.path.join(base, folder)
        prefix = f'/static/imagens/{folder}'
    if not os.path.exists(target):
        return jsonify({'fotos': []})
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.gif')
    VIDEO_EXTS = ('.mp4', '.webm', '.mov')
    items = []
    for f in os.listdir(target):
        if not os.path.isfile(os.path.join(target, f)):
            continue
        lower = f.lower()
        if lower.endswith(IMAGE_EXTS):
            items.append({'url': f'{prefix}/{f}', 'type': 'image'})
        elif lower.endswith(VIDEO_EXTS):
            items.append({'url': f'{prefix}/{f}', 'type': 'video'})
    return jsonify({'fotos': items})



@app.route('/upload', methods=['POST'])
def upload_files():
    if 'images' not in request.files:
        return jsonify({'status': 'error', 'message': 'Nenhum arquivo enviado'}), 400
    
    folder = request.form.get('folder', 'Geral')
    base = app.config['IMAGE_FOLDER']
    if folder == 'Geral':
        target_dir = base
    else:
        target_dir = os.path.join(base, folder)
        os.makedirs(target_dir, exist_ok=True)
    
    files = request.files.getlist('images')
    saved_files = []
    max_size = (1920, 1080)  # Full HD - ótimo para projeção
    
    for file in files:
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Nome de arquivo vazio'}), 400
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext in ('.mp4', '.webm', '.mov'):
            file_path = os.path.join(target_dir, file.filename)
            file.save(file_path)
            saved_files.append(file.filename)
        elif file_ext == '.pdf':
            # Converter PDF para imagens otimizadas para projeção
            pdf_document = fitz.open(stream=file.read(), filetype="pdf")
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]

                # Renderiza em 2x para boa qualidade inicial
                matrix = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=matrix)

                # Converte para PIL para redimensionar e comprimir
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail(max_size, Image.LANCZOS)

                # Salva como JPEG otimizado (muito mais leve que PNG)
                img_path = os.path.join(target_dir, f"{os.path.splitext(file.filename)[0]}_page-{str(page_num + 1).zfill(4)}.jpg")
                img.save(img_path, 'JPEG', quality=85, optimize=True)
                saved_files.append(os.path.basename(img_path))
        elif file_ext == '.pptx':
            import subprocess, tempfile
            with tempfile.TemporaryDirectory() as tmp:
                pptx_path = os.path.join(tmp, file.filename)
                file.save(pptx_path)
                subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, pptx_path],
                    capture_output=True, timeout=120
                )
                pdf_path = os.path.splitext(pptx_path)[0] + '.pdf'
                if not os.path.exists(pdf_path):
                    continue
                pdf_document = fitz.open(pdf_path)
                base_name = os.path.splitext(file.filename)[0]
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    matrix = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=matrix)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.thumbnail(max_size, Image.LANCZOS)
                    img_path = os.path.join(target_dir, f"{base_name}_slide-{str(page_num + 1).zfill(4)}.jpg")
                    img.save(img_path, 'JPEG', quality=85, optimize=True)
                    saved_files.append(os.path.basename(img_path))
        else:
            # Salvar e redimensionar imagens com compressão otimizada
            file_path = os.path.join(target_dir, file.filename)
            with Image.open(file) as img:
                # Converte para RGB se for RGBA (PNG com transparência)
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (0, 0, 0))  # Fundo preto
                    background.paste(img, mask=img.split()[3])  # Alpha channel
                    img = background
                
                # Redimensiona mantendo proporção
                img.thumbnail(max_size, Image.LANCZOS)
                
                # Salva com compressão otimizada
                if file_ext in ['.jpg', '.jpeg']:
                    img.save(file_path, 'JPEG', quality=85, optimize=True)
                elif file_ext == '.png':
                    img.save(file_path, 'PNG', optimize=True, compress_level=6)
                else:
                    img.save(file_path, quality=85, optimize=True)
                    
            saved_files.append(file.filename)
    
    return jsonify({'status': 'success', 'saved_files': saved_files}), 200

# Rota para deletar imagens (suporta ?folder=nome)
@app.route('/delete_image', methods=['POST'])
def delete_image():
    image_name = request.json.get('image_name')
    folder = request.json.get('folder', 'Geral')
    if not image_name:
        return jsonify({'status': 'error', 'message': 'Nome de imagem não fornecido.'}), 400

    base = app.config['IMAGE_FOLDER']
    target_dir = base if folder == 'Geral' else os.path.join(base, folder)
    image_path = os.path.join(target_dir, image_name)
    if os.path.exists(image_path):
        os.remove(image_path)
        return jsonify({'status': 'success', 'message': 'Imagem deletada com sucesso.'})
    else:
        return jsonify({'status': 'error', 'message': 'Imagem não encontrada.'})

# Rota para deletar múltiplas imagens (suporta folder)
@app.route('/delete_images', methods=['POST'])
@login_required
def delete_images():
    image_names = request.json.get('image_names', [])
    folder = request.json.get('folder', 'Geral')
    if not image_names:
        return jsonify({'status': 'error', 'message': 'Nenhuma imagem selecionada.'}), 400

    base = app.config['IMAGE_FOLDER']
    target_dir = base if folder == 'Geral' else os.path.join(base, folder)
    deleted = []
    errors = []
    for name in image_names:
        image_path = os.path.join(target_dir, name)
        if os.path.exists(image_path):
            os.remove(image_path)
            deleted.append(name)
        else:
            errors.append(name)

    return jsonify({'status': 'success', 'deleted': deleted, 'errors': errors})

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
    global _display_state_cache, _video_state, _last_static_media_url, _current_display_mode, _last_image_url
    image_url = data['image_url']

    # Imagem substituiu o vídeo no monitor: limpa estado de reprodução
    _video_state['url'] = None
    _video_state['paused'] = False
    _video_state['position_offset'] = 0.0

    # Atualiza modo imediatamente (antes de qualquer retorno antecipado)
    _last_image_url = image_url
    _current_display_mode = 'image'
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
    _last_static_media_url = image_url

    # Atualiza cache
    _display_state_cache['data'] = {'url1': image_url, 'url2': ''}
    _display_state_cache['timestamp'] = time.time()

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
    global _display_state_cache, _video_state, _last_static_media_url, _current_display_mode
    video_url = data.get('video_url')
    logger.debug(f'🎬 [show_video] recebido: {video_url}')
    if not video_url:
        return

    _display_state_cache['data'] = {'url1': video_url, 'url2': '', 'media_type': 'video'}
    _display_state_cache['timestamp'] = time.time()

    # Inicia novo vídeo: zera estado de reprodução
    _video_state['url'] = video_url
    _video_state['started_at'] = time.time()
    _video_state['position_offset'] = 0.0
    _video_state['paused'] = False

    _last_static_media_url = video_url
    _current_display_mode = 'video'
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
    global _video_state
    paused = bool(data.get('paused'))
    logger.debug(f'⏯️ [toggle_video_pause] paused={paused}')

    if _video_state['url']:
        if paused and not _video_state['paused']:
            # Pausando: congela posição atual no offset
            _video_state['position_offset'] += time.time() - _video_state['started_at']
            _video_state['paused'] = True
        elif not paused and _video_state['paused']:
            # Retomando: started_at = agora; offset preservado
            _video_state['started_at'] = time.time()
            _video_state['paused'] = False

    emit('video_pause', {'paused': paused}, broadcast=True, skip_sid=_skip_sids(data))


@socketio.on('restart_video')
def handle_restart_video(data):
    """Reinicia o vídeo atual no monitor (/img) do início."""
    global _video_state
    logger.debug('⏮️ [restart_video] recebido')
    if _video_state['url']:
        _video_state['started_at'] = time.time()
        _video_state['position_offset'] = 0.0
        _video_state['paused'] = False
    emit('video_restart', {}, broadcast=True)


@socketio.on('seek_video')
def handle_seek_video(data):
    """Posiciona o vídeo do monitor em um tempo específico (segundos)."""
    global _video_state
    try:
        target = max(0.0, float(data.get('time', 0)))
    except (TypeError, ValueError):
        return
    logger.debug(f'⏩ [seek_video] time={target:.2f}s')
    if _video_state['url']:
        # Mantém estado de pause: se está pausado, só atualiza o offset; se está
        # tocando, redefine started_at para "agora" com o novo offset.
        _video_state['position_offset'] = target
        _video_state['started_at'] = time.time()
        # paused permanece como está
    emit('video_seek', {'time': target}, broadcast=True)


@app.route('/video_state')
def video_state():
    """
    Retorna o estado atual de reprodução de vídeo. Usado por novas janelas /img
    para sincronizar a posição do vídeo com as janelas já abertas.
    """
    return jsonify({
        'url': _video_state['url'],
        'position': _video_current_position(),
        'paused': _video_state['paused'],
    })


# ── Monitor de Palco ─────────────────────────────────────────────────────────

def _get_monitor_sids():
    return [sid for sid, info in socketio_clients_by_sid.items()
            if info.get('role') == 'monitor']

def _skip_sids(data):
    """Se data.exclude_monitor for true (Modo Público), retorna os sids do
    monitor de palco para excluí-los do broadcast — o monitor fica congelado."""
    return _get_monitor_sids() if data.get('exclude_monitor') else None

@socketio.on('show_monitor_content')
def handle_show_monitor_content(data):
    """Exibe URL/imagem apenas no /monitor, sem afetar o público."""
    global _current_display_mode, _last_lyrics_payload
    url = data.get('url', '')
    # O botão "Letra" manda o /monitor recarregar '/lyrics/display/public' num
    # iframe. Essa página, ao carregar do zero, busca /api/current-display pra
    # saber o que mostrar — e sem isto aqui, ela mostra o que foi exibido por
    # último de verdade ao público (ex: relógio), não a letra atual.
    # _last_lyrics_payload some a cada restart do servidor, então reconstrói a
    # partir do banco (song_id + section_index), igual ao fallback que
    # /api/current-display já usa quando não há payload em memória.
    if url == '/lyrics/display/public':
        with app.app_context():
            state = LyricsState.query.first()
            if state and state.song_id:
                song = next((s for s in load_songs() if s['id'] == state.song_id), None)
                if song and 0 <= state.section_index < len(song['sections']):
                    section = song['sections'][state.section_index]
                    _last_lyrics_payload = {'title': section['title'], 'text': section['text'][0]}
                    _current_display_mode = 'lyrics'
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
    if _video_state['url']:
        pos = _video_current_position()
        for sid in sids:
            socketio.emit('display_monitor_video', {'video_url': _video_state['url']}, to=sid)
            socketio.emit('video_seek', {'time': pos}, to=sid)
            if _video_state['paused']:
                socketio.emit('video_pause', {'paused': True}, to=sid)
    elif _display_state_cache.get('data'):
        state = _display_state_cache['data']
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
    global _display_state_cache, _video_state

    url1 = data['url1'] or ''
    url2 = data['url2'] or ''

    # Detecta media_type de url1 pela extensão
    url1_lower = url1.lower().split('?')[0]
    if url1_lower.endswith(('.mp4', '.webm', '.mov')):
        media_type = 'video'
    else:
        media_type = 'image'

    # Tela dividida substituiu o vídeo: limpa estado de reprodução
    _video_state['url'] = None
    _video_state['paused'] = False
    _video_state['position_offset'] = 0.0

    # Envia para clientes primeiro (não espera banco)
    emit('display_two_urls', {'url1': url1, 'url2': url2}, broadcast=True, skip_sid=_skip_sids(data))
    append_display_log({'type': 'image', 'title': url1 + (' + ' + url2 if url2 else '')})

    # Para salvar no banco, substitui '/img' pela URL real da última imagem salva
    def _resolve_img_url(u):
        if u != '/img':
            return u
        cached = _display_state_cache.get('data') or {}
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
    global _last_lyrics_payload, _current_display_mode
    logger.debug(f'📨 Recebido update_lyrics: {data.get("title", "Sem título")}')
    _last_lyrics_payload = data
    _current_display_mode = 'lyrics'
    emit('update_lyrics', data, broadcast=True)

@app.route('/api/current-display')
def api_current_display():
    if _current_display_mode == 'image' and _last_image_url:
        is_static = _last_image_url.startswith('/static/') or \
            bool(__import__('re').search(r'\.(jpe?g|png|gif|bmp|webp|mp4|webm|mov)(\?|$)', _last_image_url, __import__('re').I))
        return jsonify({'mode': 'image', 'image_url': _last_image_url, 'is_static': is_static})
    if _current_display_mode == 'video' and _last_static_media_url:
        return jsonify({'mode': 'video', 'video_url': _last_static_media_url})
    if _current_display_mode == 'lyrics' and _last_lyrics_payload:
        return jsonify({'mode': 'lyrics', **_last_lyrics_payload})
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


@socketio.on('screen_share_start')
def relay_screen_share_start(data):
    target = data.get('target', 'all')
    payload = {'from_sid': request.sid}
    if target == 'public':    emit('screen_share_start', payload, to='public')
    elif target == 'monitor': emit('screen_share_start', payload, to='monitor')
    else:                     emit('screen_share_start', payload, broadcast=True)

@socketio.on('screen_share_stop')
def relay_screen_share_stop(data):
    emit('screen_share_stop', {}, broadcast=True)

@socketio.on('screen_share_request')
def relay_screen_share_request(data):
    emit('screen_share_request', {'from_sid': request.sid}, to=data['broadcaster_sid'])

@socketio.on('screen_share_offer')
def relay_screen_share_offer(data):
    emit('screen_share_offer', {'sdp': data['sdp'], 'from_sid': request.sid}, to=data['target_sid'])

@socketio.on('screen_share_answer')
def relay_screen_share_answer(data):
    emit('screen_share_answer', {'sdp': data['sdp'], 'from_sid': request.sid}, to=data['target_sid'])

@socketio.on('screen_share_ice')
def relay_screen_share_ice(data):
    emit('screen_share_ice', {'candidate': data['candidate'], 'from_sid': request.sid}, to=data['target_sid'])

@app.route('/historico')
@login_required
def historico():
    return render_template('historico.html')

@app.route('/api/historico')
@login_required
def api_historico():
    log = load_display_log()
    log.reverse()
    return jsonify(log)

@app.route('/api/historico', methods=['DELETE'])
@login_required
def api_historico_clear():
    try:
        with open(DISPLAY_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f)
    except Exception:
        pass
    return jsonify({'ok': True})

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



# === Rota de teste ===
@app.route('/')
def home():
    return "Servidor Flask com mDNS ativo!"


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