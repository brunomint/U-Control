from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
)
from werkzeug.routing import BaseConverter
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
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

app = Flask(__name__)


class DateSlugConverter(BaseConverter):
    """Converte datas no formato YYYY-MM-DD (evita conflito com /agenda/edit)."""
    regex = r"\d{4}-\d{2}-\d{2}"


app.url_map.converters["dateslug"] = DateSlugConverter
texto = "Acessar ucontrol"
PORTA = 8585
MDNS_NOME = "ucontrol"
MDNS_DOMINIO = f"{MDNS_NOME}.local."
socketio = SocketIO(app, 
                    cors_allowed_origins="*",
                    async_mode='threading',
                    logger=False,
                    engineio_logger=False,
                    ping_timeout=60,
                    ping_interval=25,
                    max_http_buffer_size=1000000,
                    allow_upgrades=True,
                    transports=['polling', 'websocket'])

socketio_clients_connected = 0
socketio_clients_by_sid = {}
app.secret_key = os.urandom(24)  # Gera uma chave secreta aleatória
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Caminho para o banco de dados
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_NAME'] = 'session'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

# Configuração do banco de dados
db = SQLAlchemy(app)

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelo de Usuário no Banco de Dados
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

# Modelo para persistir estado do display
class DisplayState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url1 = db.Column(db.String(500), nullable=True)
    url2 = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

# Modelo para persistir estado das letras (música + seção)
class LyricsState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, nullable=True)  # ID da música atual
    section_index = db.Column(db.Integer, default=0)  # Índice da seção atual
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

# Criar o banco de dados e tabelas
with app.app_context():
    db.create_all()

# Cache simples em memória para reduzir queries no banco
_display_state_cache = {'data': None, 'timestamp': 0}
_cache_ttl = 5  # Cache válido por 5 segundos

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe.')
        else:
            # Use pbkdf2:sha256 como método de hash
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro realizado com sucesso!')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/api/culto/status', methods=['GET'])
@login_required
def api_culto_status():
    today = date.today().isoformat()
    orders = load_orders()
    order = orders.get(today)

    if not order or not order.get('itens'):
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

@app.route('/dashboard')
@login_required
def dashboard():
    # Busca as 3 músicas mais recentes (ordenadas por last_played)
    songs = load_songs()
    
    # Filtra músicas que têm last_played e ordena
    recent_songs = [s for s in songs if s.get('last_played')]
    recent_songs.sort(key=lambda x: x.get('last_played', ''), reverse=True)
    recent_songs = recent_songs[:3]  # Pega as 3 mais recentes
    
    return render_template('dashboard.html', recent_songs=recent_songs)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # Limpa qualquer dado da sessão
    return redirect(url_for('login'))

@app.route('/usuarios')
@login_required
def visualizar_usuarios():
    # Buscar todos os usuários no banco de dados
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/remover_usuario/<int:id>', methods=['POST'])
@login_required
def remover_usuario(id):
    usuario = User.query.get(id)
    if usuario:
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuário removido com sucesso.')
    else:
        flash('Usuário não encontrado.')
    return redirect(url_for('visualizar_usuarios'))

@app.route('/adicionar_usuario', methods=['POST'])
@login_required
def adicionar_usuario():
    username = request.form['username']
    password = request.form['password']
    
    # Verifica se o nome de usuário já existe
    if User.query.filter_by(username=username).first():
        flash('Usuário já existe.')
    else:
        # Criptografa a senha
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário adicionado com sucesso!')
    
    return redirect(url_for('visualizar_usuarios'))







# QR CODE

# Defina a porta que você deseja usar
porta = 8585

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
        if rota == "/":
            url_completa = f"http://{ip_local}:{porta}/"
            nome_arquivo = "root_qr_code.png"  # Nome especial para a rota "/"
        else:
            url_completa = f"http://{ip_local}:{porta}/{rota}"
            nome_arquivo = f"{rota.replace('/', '_')}_qr_code.png"  # Substitui '/' por '_' no nome do arquivo

        caminho_arquivo = os.path.join(caminho_pasta, nome_arquivo)

        # Gerar o QR Code e salvar
        qr_code = qrcode.make(url_completa)
        qr_code.save(caminho_arquivo)
        print(f"QR Code para '{url_completa}' salvo em: {caminho_arquivo}")

# Lista de rotas para as quais você quer gerar QR Codes
rotas = ["/", "songs", "lyrics/display", "monitor", "img", "presenter", "help", "order", "view", "bible", "bible/display"]

def gerar_links(rotas):
    ip_local = obter_endereco_ip()
    links = []

    for rota in rotas:
        if rota == "/":
            url_completa = f"http://{ip_local}:{porta}/"
        else:
            url_completa = f"http://{ip_local}:{porta}/{rota}"
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
    porta_url = f"http://{ip_local}:{porta}"
    
    dados = []
    for rota, nome in rotas:
        if rota == "/":
            url = f"{porta_url}/"
            nome_arquivo = "root_qr_code"
        else:
            url = f"{porta_url}/{rota}"
            nome_arquivo = rota.replace("/", "_") + "_qr_code"
        dados.append({
            "url": url,
            "nome": nome,
            "img": f"/static/qrcodes/{nome_arquivo}.png",
            "img_id": nome_arquivo
        })
    
    return render_template("links.html", dados=dados)




#Extrair Cifras do Cifra-CLub
@app.route("/cifra")
def pegar_cifra():
    url = request.args.get("url")
    if not url:
        return "URL não fornecida", 400

    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')

        # Título
        titulo_tag = soup.find('h1', class_='t1')
        titulo = titulo_tag.text.strip() if titulo_tag else 'Título não encontrado'

        # Compositor
        compositor_tag = soup.find('h2', class_='t3')
        compositor = compositor_tag.text.strip() if compositor_tag else 'Compositor não encontrado'

        # Cifra
        cifra_tag = soup.select_one('.cifra_cnt')
        cifra = cifra_tag.get_text().strip() if cifra_tag else 'Cifra não encontrada'

        # Monta texto puro com título e compositor na frente, separados por linhas em branco
        texto_puro = f"{titulo}\n\n{compositor}\n\n{cifra}"

        return texto_puro

    except Exception as e:
        return str(e), 500

# Extrair Cifra com Vídeo do Cifra Club (retorna JSON)
@app.route("/cifra_com_video")
def pegar_cifra_com_video():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')

        # Título
        titulo_tag = soup.find('h1', class_='t1')
        titulo = titulo_tag.text.strip() if titulo_tag else 'Título não encontrado'

        # Compositor
        compositor_tag = soup.find('h2', class_='t3')
        compositor = compositor_tag.text.strip() if compositor_tag else 'Compositor não encontrado'

        # Cifra
        cifra_tag = soup.select_one('.cifra_cnt')
        cifra = cifra_tag.get_text().strip() if cifra_tag else 'Cifra não encontrada'

        # Extrair URL do vídeo do YouTube
        video_url = None
        
        # Método 1: Procura iframe do YouTube
        iframe = soup.find('iframe', src=re.compile(r'youtube\.com|youtu\.be'))
        if iframe and iframe.get('src'):
            src = iframe.get('src')
            # Extrai o ID do vídeo
            match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})', src)
            if match:
                video_url = f"https://www.youtube.com/watch?v={match.group(1)}"
        
        # Método 2: Procura data-video ou atributos com ID do YouTube
        if not video_url:
            video_element = soup.find(attrs={'data-video': True})
            if video_element:
                video_id = video_element.get('data-video')
                if video_id and len(video_id) == 11:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Método 3: Procura no script da página por IDs de vídeo
        if not video_url:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Procura padrões de ID do YouTube no JavaScript
                    match = re.search(r'["\']videoId["\']\s*:\s*["\']([a-zA-Z0-9_-]{11})["\']', script.string)
                    if match:
                        video_url = f"https://www.youtube.com/watch?v={match.group(1)}"
                        break
                    # Procura URLs do YouTube diretamente
                    match = re.search(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', script.string)
                    if match:
                        video_url = f"https://www.youtube.com/watch?v={match.group(1)}"
                        break

        # Monta texto puro
        texto_puro = f"{titulo}\n\n{compositor}\n\n{cifra}"

        return jsonify({
            "titulo": titulo,
            "compositor": compositor,
            "cifra": texto_puro,
            "video_url": video_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Download de áudio do YouTube via yt-dlp
@app.route("/download_audio", methods=["POST"])
def download_audio():
    import subprocess
    
    data = request.get_json()
    video_url = data.get("url")
    song_id = data.get("song_id")  # ID da música para nomear o arquivo
    old_audio_url = data.get("old_audio_url")  # URL do áudio antigo para deletar
    
    if not video_url:
        return jsonify({"error": "URL não fornecida"}), 400
    
    try:
        # Extrai ID do vídeo para nome do arquivo
        match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', video_url)
        if not match:
            return jsonify({"error": "URL do YouTube inválida"}), 400
        
        video_id = match.group(1)
        
        # Define nome do arquivo (usa song_id se fornecido, senão video_id)
        filename = f"{song_id}_{video_id}" if song_id else video_id
        audio_dir = os.path.join(app.static_folder, 'audio')
        output_path = os.path.join(audio_dir, f"{filename}.mp3")
        
        # Deleta áudio antigo se fornecido e diferente do novo
        if old_audio_url and old_audio_url.strip():
            old_filename = old_audio_url.replace('/static/audio/', '')
            old_path = os.path.join(audio_dir, old_filename)
            if os.path.exists(old_path) and old_path != output_path:
                os.remove(old_path)
                print(f"🗑️ Áudio antigo deletado: {old_path}", flush=True)
        
        # Verifica se já existe
        if os.path.exists(output_path):
            return jsonify({
                "success": True,
                "audio_url": f"/static/audio/{filename}.mp3",
                "message": "Áudio já existe"
            })
        
        # Garante que a pasta existe
        os.makedirs(audio_dir, exist_ok=True)
        
        # Comando yt-dlp para baixar apenas áudio em MP3
        cmd = [
            "python3", "-m", "yt_dlp",
            "-x",  # Extrai áudio
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", output_path.replace('.mp3', '.%(ext)s'),
            "--no-playlist",
            "--quiet",
            video_url
        ]
        
        print(f"🎵 Baixando áudio: {video_url}", flush=True)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"❌ Erro yt-dlp: {result.stderr}", flush=True)
            return jsonify({"error": f"Erro ao baixar: {result.stderr}"}), 500
        
        # Verifica se o arquivo foi criado
        if os.path.exists(output_path):
            print(f"✅ Áudio salvo: {output_path}", flush=True)
            return jsonify({
                "success": True,
                "audio_url": f"/static/audio/{filename}.mp3"
            })
        else:
            return jsonify({"error": "Arquivo não foi criado"}), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout ao baixar áudio"}), 500
    except Exception as e:
        print(f"❌ Erro: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500


# Listar áudios disponíveis
@app.route("/list_audio")
def list_audio():
    audio_dir = os.path.join(app.static_folder, 'audio')
    if not os.path.exists(audio_dir):
        return jsonify({"audios": []})
    
    audios = []
    for f in os.listdir(audio_dir):
        if f.endswith('.mp3'):
            audios.append({
                "filename": f,
                "url": f"/static/audio/{f}"
            })
    
    return jsonify({"audios": audios})


# Deletar áudio
@app.route("/delete_audio/<filename>", methods=["DELETE"])
@login_required
def delete_audio(filename):
    audio_path = os.path.join(app.static_folder, 'audio', filename)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        return jsonify({"success": True})
    return jsonify({"error": "Arquivo não encontrado"}), 404





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






# --- Funções Para Bíblia ---

# Cache para Bíblias carregadas
_bible_cache = {}
_bible_metadata = None

# Arquivo de configurações
SETTINGS_FILE = os.path.join(os.getcwd(), 'settings.json')

def load_settings():
    """Carrega as configurações do arquivo JSON."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(settings):
    """Salva as configurações no arquivo JSON."""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def get_preferred_translation():
    """Retorna a tradução preferida da Bíblia."""
    settings = load_settings()
    return settings.get('bible_translation', 'acf')

def set_preferred_translation(translation):
    """Salva a tradução preferida da Bíblia."""
    settings = load_settings()
    settings['bible_translation'] = translation
    save_settings(settings)

def load_bible_metadata():
    """Carrega os metadados dos livros da Bíblia."""
    global _bible_metadata
    if _bible_metadata is None:
        metadata_path = os.path.join(os.getcwd(), 'bibles', 'books_metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                _bible_metadata = json.load(f)
        else:
            _bible_metadata = {"translations": {}, "books": []}
    return _bible_metadata

def load_bible(translation='acf'):
    """Carrega uma tradução da Bíblia do arquivo JSON."""
    global _bible_cache
    if translation not in _bible_cache:
        bible_path = os.path.join(os.getcwd(), 'bibles', f'{translation}.json')
        if os.path.exists(bible_path):
            with open(bible_path, 'r', encoding='utf-8-sig') as f:
                _bible_cache[translation] = json.load(f)
        else:
            _bible_cache[translation] = []
    return _bible_cache[translation]

def get_book_name(abbrev):
    """Retorna o nome completo do livro pela abreviação."""
    metadata = load_bible_metadata()
    for book in metadata.get('books', []):
        if book['abbrev'] == abbrev:
            return book['name']
    return abbrev.upper()

def generate_bible_url(reference):
    """Gera URL de controle a partir de uma referência bíblica."""
    import re
    
    # Mapeamento de nomes para abreviações
    book_map = {
        'gênesis': 'gn', 'genesis': 'gn', 'gn': 'gn',
        'êxodo': 'ex', 'exodo': 'ex', 'ex': 'ex',
        'levítico': 'lv', 'levitico': 'lv', 'lv': 'lv',
        'números': 'nm', 'numeros': 'nm', 'nm': 'nm',
        'deuteronômio': 'dt', 'deuteronomio': 'dt', 'dt': 'dt',
        'josué': 'js', 'josue': 'js', 'js': 'js',
        'juízes': 'jz', 'juizes': 'jz', 'jz': 'jz',
        'rute': 'rt', 'rt': 'rt',
        '1 samuel': '1sm', '1samuel': '1sm', '1sm': '1sm', '1 sm': '1sm',
        '2 samuel': '2sm', '2samuel': '2sm', '2sm': '2sm', '2 sm': '2sm',
        '1 reis': '1rs', '1reis': '1rs', '1rs': '1rs', '1 rs': '1rs',
        '2 reis': '2rs', '2reis': '2rs', '2rs': '2rs', '2 rs': '2rs',
        '1 crônicas': '1cr', '1 cronicas': '1cr', '1cr': '1cr', '1 cr': '1cr',
        '2 crônicas': '2cr', '2 cronicas': '2cr', '2cr': '2cr', '2 cr': '2cr',
        'esdras': 'ed', 'ed': 'ed',
        'neemias': 'ne', 'ne': 'ne',
        'ester': 'et', 'et': 'et',
        'jó': 'job', 'job': 'job',
        'salmos': 'sl', 'salmo': 'sl', 'sl': 'sl',
        'provérbios': 'pv', 'proverbios': 'pv', 'pv': 'pv',
        'eclesiastes': 'ec', 'ec': 'ec',
        'cantares': 'ct', 'cânticos': 'ct', 'canticos': 'ct', 'ct': 'ct',
        'isaías': 'is', 'isaias': 'is', 'is': 'is',
        'jeremias': 'jr', 'jr': 'jr',
        'lamentações': 'lm', 'lamentacoes': 'lm', 'lm': 'lm',
        'ezequiel': 'ez', 'ez': 'ez',
        'daniel': 'dn', 'dn': 'dn',
        'oséias': 'os', 'oseias': 'os', 'os': 'os',
        'joel': 'jl', 'jl': 'jl',
        'amós': 'am', 'amos': 'am', 'am': 'am',
        'obadias': 'ob', 'ob': 'ob',
        'jonas': 'jn', 'jn': 'jn',
        'miquéias': 'mq', 'miqueias': 'mq', 'mq': 'mq',
        'naum': 'na', 'na': 'na',
        'habacuque': 'hc', 'hc': 'hc',
        'sofonias': 'sf', 'sf': 'sf',
        'ageu': 'ag', 'ag': 'ag',
        'zacarias': 'zc', 'zc': 'zc',
        'malaquias': 'ml', 'ml': 'ml',
        'mateus': 'mt', 'mt': 'mt',
        'marcos': 'mc', 'mc': 'mc',
        'lucas': 'lc', 'lc': 'lc',
        'joão': 'jo', 'joao': 'jo',
        'atos': 'at', 'at': 'at',
        'romanos': 'rm', 'rm': 'rm',
        '1 coríntios': '1co', '1 corintios': '1co', '1co': '1co', '1 co': '1co',
        '2 coríntios': '2co', '2 corintios': '2co', '2co': '2co', '2 co': '2co',
        'gálatas': 'gl', 'galatas': 'gl', 'gl': 'gl',
        'efésios': 'ef', 'efesios': 'ef', 'ef': 'ef',
        'filipenses': 'fp', 'fp': 'fp',
        'colossenses': 'cl', 'cl': 'cl',
        '1 tessalonicenses': '1ts', '1ts': '1ts', '1 ts': '1ts',
        '2 tessalonicenses': '2ts', '2ts': '2ts', '2 ts': '2ts',
        '1 timóteo': '1tm', '1 timoteo': '1tm', '1tm': '1tm', '1 tm': '1tm',
        '2 timóteo': '2tm', '2 timoteo': '2tm', '2tm': '2tm', '2 tm': '2tm',
        'tito': 'tt', 'tt': 'tt',
        'filemom': 'fm', 'fm': 'fm',
        'hebreus': 'hb', 'hb': 'hb',
        'tiago': 'tg', 'tg': 'tg',
        '1 pedro': '1pe', '1pe': '1pe', '1 pe': '1pe',
        '2 pedro': '2pe', '2pe': '2pe', '2 pe': '2pe',
        '1 joão': '1jo', '1 joao': '1jo', '1jo': '1jo', '1 jo': '1jo',
        '2 joão': '2jo', '2 joao': '2jo', '2jo': '2jo', '2 jo': '2jo',
        '3 joão': '3jo', '3 joao': '3jo', '3jo': '3jo', '3 jo': '3jo',
        'judas': 'jd', 'jd': 'jd',
        'apocalipse': 'ap', 'ap': 'ap'
    }
    
    # Regex para capturar: livro capítulo:versículo(s)
    regex = r'^(.+?)\s*(\d+)(?:\s*:\s*(\d+)(?:\s*-\s*(\d+))?)?$'
    match = re.match(regex, reference, re.IGNORECASE)
    
    if not match:
        return f'/bible?search={reference}'
    
    book_name = match.group(1).strip().lower()
    chapter = match.group(2)
    verse_start = match.group(3)
    verse_end = match.group(4)
    
    book_abbrev = book_map.get(book_name)
    if not book_abbrev:
        return f'/bible?search={reference}'
    
    url = f'/bible/control/{book_abbrev}/{chapter}'
    if verse_start:
        if verse_end and verse_end != verse_start:
            url += f'/{verse_start}-{verse_end}'
        else:
            url += f'/{verse_start}'
    
    return url

# Mapeamento de abreviações equivalentes entre diferentes traduções
ABBREV_ALIASES = {
    'sl': ['ps', 'salmos', 'salmo'],      # Salmos
    'ps': ['sl', 'salmos', 'salmo'],
    'jz': ['jud', 'juizes'],               # Juízes
    'jud': ['jz', 'juizes'],
    'ct': ['ss', 'canticos', 'cantares'],  # Cantares
    'ss': ['ct', 'canticos', 'cantares'],
    'lm': ['la', 'lamentacoes'],           # Lamentações
    'la': ['lm', 'lamentacoes'],
    'am': ['amos'],                         # Amós
    'ob': ['obadias', 'abd'],               # Obadias
    'mq': ['mi', 'miqueias'],               # Miquéias
    'mi': ['mq', 'miqueias'],
    'na': ['naum'],                         # Naum
    'hc': ['hab', 'habacuque'],             # Habacuque
    'hab': ['hc', 'habacuque'],
    'sf': ['zep', 'sofonias'],              # Sofonias
    'zep': ['sf', 'sofonias'],
    'ag': ['hag', 'ageu'],                  # Ageu
    'hag': ['ag', 'ageu'],
    'zc': ['zec', 'zacarias'],              # Zacarias
    'zec': ['zc', 'zacarias'],
    'ml': ['mal', 'malaquias'],             # Malaquias
    'mal': ['ml', 'malaquias'],
    'mt': ['mat', 'mateus'],                # Mateus
    'mat': ['mt', 'mateus'],
    'mc': ['mr', 'marcos'],                 # Marcos
    'mr': ['mc', 'marcos'],
    'lc': ['lk', 'lucas'],                  # Lucas
    'lk': ['lc', 'lucas'],
    'jo': ['jn', 'joao'],                   # João
    'jn': ['jo', 'joao'],
    'at': ['acts', 'atos'],                 # Atos
    'acts': ['at', 'atos'],
    'rm': ['rom', 'romanos'],               # Romanos
    'rom': ['rm', 'romanos'],
    '1co': ['1cor', '1corintios'],          # 1 Coríntios
    '1cor': ['1co', '1corintios'],
    '2co': ['2cor', '2corintios'],          # 2 Coríntios
    '2cor': ['2co', '2corintios'],
    'gl': ['gal', 'galatas'],               # Gálatas
    'gal': ['gl', 'galatas'],
    'ef': ['eph', 'efesios'],               # Efésios
    'eph': ['ef', 'efesios'],
    'fp': ['php', 'filipenses'],            # Filipenses
    'php': ['fp', 'filipenses'],
    'cl': ['col', 'colossenses'],           # Colossenses
    'col': ['cl', 'colossenses'],
    '1ts': ['1th', '1tessalonicenses'],     # 1 Tessalonicenses
    '1th': ['1ts', '1tessalonicenses'],
    '2ts': ['2th', '2tessalonicenses'],     # 2 Tessalonicenses
    '2th': ['2ts', '2tessalonicenses'],
    '1tm': ['1ti', '1timoteo'],             # 1 Timóteo
    '1ti': ['1tm', '1timoteo'],
    '2tm': ['2ti', '2timoteo'],             # 2 Timóteo
    '2ti': ['2tm', '2timoteo'],
    'tt': ['tit', 'tito'],                  # Tito
    'tit': ['tt', 'tito'],
    'fm': ['phm', 'filemom'],               # Filemom
    'phm': ['fm', 'filemom'],
    'hb': ['heb', 'hebreus'],               # Hebreus
    'heb': ['hb', 'hebreus'],
    'tg': ['jas', 'tiago'],                 # Tiago
    'jas': ['tg', 'tiago'],
    '1pe': ['1pt', '1pedro'],               # 1 Pedro
    '1pt': ['1pe', '1pedro'],
    '2pe': ['2pt', '2pedro'],               # 2 Pedro
    '2pt': ['2pe', '2pedro'],
    '1jo': ['1jn', '1joao'],                # 1 João
    '1jn': ['1jo', '1joao'],
    '2jo': ['2jn', '2joao'],                # 2 João
    '2jn': ['2jo', '2joao'],
    '3jo': ['3jn', '3joao'],                # 3 João
    '3jn': ['3jo', '3joao'],
    'jd': ['jude', 'judas'],                # Judas
    'jude': ['jd', 'judas'],
    'ap': ['rev', 'apocalipse'],            # Apocalipse
    'rev': ['ap', 'apocalipse'],
}

def get_book_by_abbrev(translation, abbrev):
    """Retorna um livro específico pela abreviação."""
    bible = load_bible(translation)
    abbrev_lower = abbrev.lower()
    
    # Primeiro, tenta encontrar pela abreviação exata
    for book in bible:
        if book.get('abbrev', '').lower() == abbrev_lower:
            return book
    
    # Se não encontrou, tenta pelas abreviações alternativas
    aliases = ABBREV_ALIASES.get(abbrev_lower, [])
    for alias in aliases:
        for book in bible:
            if book.get('abbrev', '').lower() == alias.lower():
                return book
    
    return None

def search_bible(translation, query, limit=50):
    """Busca versículos por texto."""
    bible = load_bible(translation)
    metadata = load_bible_metadata()
    results = []
    query_lower = query.lower()
    
    for book in bible:
        book_abbrev = book.get('abbrev', '')
        book_name = get_book_name(book_abbrev)
        chapters = book.get('chapters', [])
        
        for chapter_idx, chapter in enumerate(chapters):
            for verse_idx, verse in enumerate(chapter):
                if query_lower in verse.lower():
                    results.append({
                        'book_abbrev': book_abbrev,
                        'book_name': book_name,
                        'chapter': chapter_idx + 1,
                        'verse': verse_idx + 1,
                        'text': verse,
                        'reference': f'{book_name} {chapter_idx + 1}:{verse_idx + 1}'
                    })
                    if len(results) >= limit:
                        return results
    return results

def parse_reference(reference):
    """Parseia uma referência bíblica como 'João 3:16' ou 'Jo 3:16-18'."""
    metadata = load_bible_metadata()
    
    # Padrões: "João 3:16", "Jo 3:16", "João 3:16-18", "João 3"
    pattern = r'^(.+?)\s*(\d+)(?::(\d+)(?:-(\d+))?)?$'
    match = re.match(pattern, reference.strip())
    
    if not match:
        return None
    
    book_input = match.group(1).strip().lower()
    chapter = int(match.group(2))
    verse_start = int(match.group(3)) if match.group(3) else None
    verse_end = int(match.group(4)) if match.group(4) else verse_start
    
    # Encontra o livro pela abreviação ou nome
    book_abbrev = None
    for book in metadata.get('books', []):
        if book['abbrev'].lower() == book_input or book['name'].lower() == book_input:
            book_abbrev = book['abbrev']
            break
    
    if not book_abbrev:
        # Tenta match parcial
        for book in metadata.get('books', []):
            if book_input in book['name'].lower() or book['name'].lower().startswith(book_input):
                book_abbrev = book['abbrev']
                break
    
    if not book_abbrev:
        return None
    
    return {
        'book_abbrev': book_abbrev,
        'chapter': chapter,
        'verse_start': verse_start,
        'verse_end': verse_end
    }

# --- Rotas da Bíblia ---

@app.route('/bible')
@login_required
def bible_home():
    """Página principal da Bíblia."""
    metadata = load_bible_metadata()
    translation = request.args.get('translation') or get_preferred_translation()
    
    # Separa livros por testamento
    old_testament = [b for b in metadata.get('books', []) if b.get('testament') == 'old']
    new_testament = [b for b in metadata.get('books', []) if b.get('testament') == 'new']
    
    return render_template('bible.html', 
                         old_testament=old_testament,
                         new_testament=new_testament,
                         translations=metadata.get('translations', {}),
                         current_translation=translation)

@app.route('/bible/<book_abbrev>')
@login_required
def bible_book(book_abbrev):
    """Exibe os capítulos de um livro."""
    translation = request.args.get('translation') or get_preferred_translation()
    book = get_book_by_abbrev(translation, book_abbrev)
    
    if not book:
        flash('Livro não encontrado!', 'error')
        return redirect(url_for('bible_home'))
    
    metadata = load_bible_metadata()
    book_name = get_book_name(book_abbrev)
    num_chapters = len(book.get('chapters', []))
    
    return render_template('bible_book.html',
                         book_abbrev=book_abbrev,
                         book_name=book_name,
                         num_chapters=num_chapters,
                         translations=metadata.get('translations', {}),
                         current_translation=translation)

@app.route('/bible/<book_abbrev>/<int:chapter>')
@login_required
def bible_chapter(book_abbrev, chapter):
    """Exibe os versículos de um capítulo."""
    translation = request.args.get('translation') or get_preferred_translation()
    book = get_book_by_abbrev(translation, book_abbrev)
    
    if not book:
        flash('Livro não encontrado!', 'error')
        return redirect(url_for('bible_home'))
    
    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        flash('Capítulo não encontrado!', 'error')
        return redirect(url_for('bible_book', book_abbrev=book_abbrev))
    
    metadata = load_bible_metadata()
    book_name = get_book_name(book_abbrev)
    verses = chapters[chapter - 1]
    
    # Navegação entre capítulos
    prev_chapter = chapter - 1 if chapter > 1 else None
    next_chapter = chapter + 1 if chapter < len(chapters) else None
    
    return render_template('bible_chapter.html',
                         book_abbrev=book_abbrev,
                         book_name=book_name,
                         chapter=chapter,
                         verses=verses,
                         num_chapters=len(chapters),
                         prev_chapter=prev_chapter,
                         next_chapter=next_chapter,
                         translations=metadata.get('translations', {}),
                         current_translation=translation)

@app.route('/api/bible/search')
@login_required
def api_bible_search():
    """API para busca de versículos."""
    query = request.args.get('q', '')
    translation = request.args.get('translation', 'acf')
    
    if len(query) < 3:
        return jsonify({'error': 'Busca deve ter pelo menos 3 caracteres', 'results': []})
    
    # Primeiro tenta como referência
    ref = parse_reference(query)
    if ref:
        book = get_book_by_abbrev(translation, ref['book_abbrev'])
        if book:
            chapters = book.get('chapters', [])
            chapter_idx = ref['chapter'] - 1
            if 0 <= chapter_idx < len(chapters):
                verses = chapters[chapter_idx]
                results = []
                book_name = get_book_name(ref['book_abbrev'])
                
                if ref['verse_start']:
                    # Versículos específicos
                    start = ref['verse_start'] - 1
                    end = ref['verse_end'] if ref['verse_end'] else ref['verse_start']
                    for i in range(start, min(end, len(verses))):
                        results.append({
                            'book_abbrev': ref['book_abbrev'],
                            'book_name': book_name,
                            'chapter': ref['chapter'],
                            'verse': i + 1,
                            'text': verses[i],
                            'reference': f'{book_name} {ref["chapter"]}:{i + 1}'
                        })
                else:
                    # Capítulo inteiro
                    for i, verse in enumerate(verses):
                        results.append({
                            'book_abbrev': ref['book_abbrev'],
                            'book_name': book_name,
                            'chapter': ref['chapter'],
                            'verse': i + 1,
                            'text': verse,
                            'reference': f'{book_name} {ref["chapter"]}:{i + 1}'
                        })
                
                return jsonify({'results': results, 'type': 'reference'})
    
    # Busca por texto
    results = search_bible(translation, query)
    return jsonify({'results': results, 'type': 'text'})

@app.route('/api/bible/verse')
@login_required
def api_bible_verse():
    """API para obter versículos específicos."""
    translation = request.args.get('translation', 'acf')
    book_abbrev = request.args.get('book')
    chapter = request.args.get('chapter', type=int)
    verse_start = request.args.get('verse_start', type=int)
    verse_end = request.args.get('verse_end', type=int, default=None)
    
    if not all([book_abbrev, chapter, verse_start]):
        return jsonify({'error': 'Parâmetros inválidos'}), 400
    
    book = get_book_by_abbrev(translation, book_abbrev)
    if not book:
        return jsonify({'error': 'Livro não encontrado'}), 404
    
    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        return jsonify({'error': 'Capítulo não encontrado'}), 404
    
    verses = chapters[chapter - 1]
    book_name = get_book_name(book_abbrev)
    
    if verse_end is None:
        verse_end = verse_start
    
    result_verses = []
    for i in range(verse_start - 1, min(verse_end, len(verses))):
        result_verses.append({
            'verse': i + 1,
            'text': verses[i]
        })
    
    reference = f'{book_name} {chapter}:{verse_start}'
    if verse_end and verse_end != verse_start:
        reference += f'-{verse_end}'
    
    return jsonify({
        'book_abbrev': book_abbrev,
        'book_name': book_name,
        'chapter': chapter,
        'verses': result_verses,
        'reference': reference
    })

# Evento WebSocket para transmitir versículos da Bíblia
@socketio.on('update_bible')
def handle_update_bible(data):
    print(f'📖 Recebido update_bible: {data.get("reference", "Sem referência")}')
    emit('update_bible', data, broadcast=True)

@app.route('/bible/display')
def bible_display():
    """Página de exibição da Bíblia para projeção."""
    return render_template('bible_display.html')

@app.route('/api/bible/add_to_order', methods=['POST'])
@login_required
def api_bible_add_to_order():
    """Adiciona uma passagem bíblica à ordem do culto."""
    data = request.get_json()
    reference = data.get('reference', '').strip()
    
    if not reference:
        return jsonify({'success': False, 'error': 'Referência vazia'})
    
    # Carrega a ordem do culto
    order_file = os.path.join(os.getcwd(), 'order_of_service.json')
    order_data = []
    
    if os.path.exists(order_file):
        with open(order_file, 'r', encoding='utf-8') as f:
            order_data = json.load(f)
    
    # Cria o novo item de Bíblia
    new_item = {
        'isBible': True,
        'reference': reference,
        'title': f'📖 {reference}'
    }
    
    # Adiciona à lista
    order_data.append(new_item)
    
    # Salva o arquivo
    with open(order_file, 'w', encoding='utf-8') as f:
        json.dump(order_data, f, ensure_ascii=False, indent=4)
    
    return jsonify({'success': True, 'url': generate_bible_url(reference)})

@app.route('/api/bible/remove_from_order', methods=['POST'])
@login_required
def api_bible_remove_from_order():
    """Remove uma passagem bíblica da ordem do culto."""
    data = request.get_json()
    reference = data.get('reference', '').strip()
    
    if not reference:
        return jsonify({'success': False, 'error': 'Referência vazia'})
    
    # Carrega a ordem do culto
    order_file = os.path.join(os.getcwd(), 'order_of_service.json')
    
    if not os.path.exists(order_file):
        return jsonify({'success': False, 'error': 'Arquivo não encontrado'})
    
    with open(order_file, 'r', encoding='utf-8') as f:
        order_data = json.load(f)
    
    # Remove o item com a referência correspondente
    original_len = len(order_data)
    order_data = [item for item in order_data if not (item.get('isBible') and item.get('reference') == reference)]
    
    if len(order_data) == original_len:
        return jsonify({'success': False, 'error': 'Passagem não encontrada'})
    
    # Salva o arquivo
    with open(order_file, 'w', encoding='utf-8') as f:
        json.dump(order_data, f, ensure_ascii=False, indent=4)
    
    return jsonify({'success': True})

@app.route('/bible/control/')
@login_required
def bible_control_list():
    """Lista de passagens bíblicas da ordem do culto."""
    # Carrega a ordem do culto
    order_file = os.path.join(os.getcwd(), 'order_of_service.json')
    bible_items = []
    
    if os.path.exists(order_file):
        with open(order_file, 'r', encoding='utf-8') as f:
            order_data = json.load(f)
            # Filtra apenas itens de Bíblia
            bible_items = [item for item in order_data if item.get('isBible')]
    
    return render_template('bible_control_list.html', bible_items=bible_items)

@app.route('/api/bible/set_translation', methods=['POST'])
@login_required
def api_set_bible_translation():
    """Salva a tradução preferida da Bíblia."""
    data = request.get_json()
    translation = data.get('translation', 'acf')
    set_preferred_translation(translation)
    return jsonify({'success': True, 'translation': translation})

@app.route('/bible/control/<book_abbrev>/<int:chapter>')
@app.route('/bible/control/<book_abbrev>/<int:chapter>/<int:verse_start>')
@app.route('/bible/control/<book_abbrev>/<int:chapter>/<int:verse_start>-<int:verse_end>')
@login_required
def bible_control(book_abbrev, chapter, verse_start=None, verse_end=None):
    """Página de controle de passagem bíblica (similar ao /lyrics/)."""
    translation = request.args.get('translation') or get_preferred_translation()
    
    book = get_book_by_abbrev(translation, book_abbrev)
    if not book:
        return "Livro não encontrado", 404
    
    chapters = book.get('chapters', [])
    if chapter < 1 or chapter > len(chapters):
        return "Capítulo não encontrado", 404
    
    verses = chapters[chapter - 1]
    book_name = get_book_name(book_abbrev)
    metadata = load_bible_metadata()
    
    # Navegação entre capítulos
    prev_chapter = chapter - 1 if chapter > 1 else None
    next_chapter = chapter + 1 if chapter < len(chapters) else None
    
    # Carrega passagens bíblicas da ordem do culto
    order_file = os.path.join(os.getcwd(), 'order_of_service.json')
    bible_items = []
    if os.path.exists(order_file):
        with open(order_file, 'r', encoding='utf-8') as f:
            order_data = json.load(f)
            for item in order_data:
                if item.get('isBible'):
                    # Gera URL a partir da referência se não existir
                    if not item.get('url'):
                        item['url'] = generate_bible_url(item.get('reference', ''))
                    bible_items.append(item)
    
    return render_template('bible_control.html',
        book_abbrev=book_abbrev,
        book_name=book_name,
        chapter=chapter,
        verses=verses,
        num_chapters=len(chapters),
        prev_chapter=prev_chapter,
        next_chapter=next_chapter,
        translations=metadata.get('translations', {}),
        current_translation=translation,
        initial_verse=verse_start,
        verse_end=verse_end,
        bible_items=bible_items
    )

# --- Funções Para editor de música para exibir na tela ---

def load_songs():
    """Carrega as músicas do arquivo JSON."""
    if not os.path.exists('songs.json'):
        return []
    with open('songs.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_songs(songs):
    """Salva as músicas no arquivo JSON e atualiza a cache."""
    global songs_cache
    with open('songs.json', 'w', encoding='utf-8') as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)
    songs_cache = songs  # Atualiza a cache

def get_next_id(songs):
    """Obtém o próximo ID disponível para uma nova música."""
    return max((song['id'] for song in songs), default=0) + 1

def format_lyrics(text):
    """Formata os acordes nas letras das músicas."""
    chord_pattern = r'\b[A-G][#b]?[mM]?[7-9]?\b'
    return re.sub(chord_pattern, r'<span class="chord">\g<0></span>', text)

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
    
    print("🎼 [DEBUG] Iniciando add_song...", flush=True)
    
    title = request.form['title']
    author = request.form['author']
    sections = request.form.getlist('sections[]')
    texts = request.form.getlist('texts[]')
    
    print(f"📝 [DEBUG] Título: {title}", flush=True)
    print(f"👤 [DEBUG] Autor: {author}", flush=True)
    print(f"📄 [DEBUG] Textos: {texts}", flush=True)
    
    # Captura dados da partitura se enviados
    sheet_data_json = request.form.get('sheet_data')
    print(f"🎵 [DEBUG] Sheet data recebido: {bool(sheet_data_json)}", flush=True)
    if sheet_data_json:
        print(f"📊 [DEBUG] Tamanho dos dados: {len(sheet_data_json)} caracteres", flush=True)
        print(f"📋 [DEBUG] Primeiros 200 chars: {sheet_data_json[:200]}...", flush=True)
    
    # Captura URL do vídeo de referência
    video_url = request.form.get('video_url', '').strip()
    if video_url:
        print(f"🎬 [DEBUG] Video URL recebido: {video_url}", flush=True)
    
    # Captura URL do áudio local
    audio_url = request.form.get('audio_url', '').strip()
    if audio_url:
        print(f"🎵 [DEBUG] Audio URL recebido: {audio_url}", flush=True)

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
    
    print(f"🆔 [DEBUG] Nova música ID: {new_song['id']}", flush=True)
    
    # Se há dados de partitura, adiciona ao objeto da música
    if sheet_data_json:
        try:
            import json
            sheet_data = json.loads(sheet_data_json)
            new_song["sheet_data"] = sheet_data
            
            # Verifica se é array (múltiplas partituras) ou objeto (partitura única)
            if isinstance(sheet_data, list):
                total_notes = sum(len(s.get('notes', [])) for s in sheet_data)
                print(f"✅ [DEBUG] {len(sheet_data)} partitura(s) adicionada(s) com {total_notes} notas no total", flush=True)
            else:
                print(f"✅ [DEBUG] Sheet data adicionado com {len(sheet_data.get('notes', []))} notas", flush=True)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}", flush=True)
    
    # Verifica se alguma seção tem marcador de partitura integrada
    for section in new_song["sections"]:
        for i, text in enumerate(section["text"]):
            if "[🎼 PARTITURA_INTEGRADA]" in text:
                print(f"🔍 [DEBUG] Marcador encontrado no texto: {text}", flush=True)
                # Se há dados de partitura, substitui o marcador
                if sheet_data_json:
                    try:
                        sheet_data = json.loads(sheet_data_json)
                        new_song["sheet_data"] = sheet_data
                        print(f"✅ [DEBUG] Dados da partitura processados e salvos", flush=True)
                        # Remove o marcador do texto
                        section["text"][i] = text.replace("[🎼 PARTITURA_INTEGRADA]", "").strip()
                        # Remove linhas vazias resultantes
                        section["text"] = [t for t in section["text"] if t.strip()]
                        print(f"🧹 [DEBUG] Marcador removido do texto", flush=True)
                    except Exception as e:
                        print(f"❌ [DEBUG] Erro ao processar marcador: {e}", flush=True)
                break
    
    print(f"💾 [DEBUG] Salvando música com sheet_data: {bool(new_song.get('sheet_data'))}", flush=True)
    if new_song.get('sheet_data'):
        sheet_data = new_song['sheet_data']
        if isinstance(sheet_data, list):
            total_notes = sum(len(s.get('notes', [])) for s in sheet_data)
            print(f"📊 [DEBUG] {len(sheet_data)} partitura(s) na música final com {total_notes} notas no total", flush=True)
        else:
            print(f"📊 [DEBUG] Notas na música final: {len(sheet_data.get('notes', []))}", flush=True)
    
    songs.append(new_song)
    save_songs(songs)
    
    print(f"✅ [DEBUG] Música salva com sucesso!", flush=True)
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
        
        print(f"🔄 [DEBUG] Editando música ID: {song_id}", flush=True)
        if video_url:
            print(f"🎬 [DEBUG] Video URL: {video_url}", flush=True)
        if audio_url:
            print(f"🎵 [DEBUG] Audio URL: {audio_url}", flush=True)
        print(f"📝 [DEBUG] Título: {title}", flush=True)
        print(f"👤 [DEBUG] Autor: {author}", flush=True)
        print(f"📋 [DEBUG] Seções recebidas: {len(sections)}", flush=True)
        print(f"📄 [DEBUG] Textos recebidos: {len(texts)}", flush=True)
        # DEBUG: Mostra espaços no primeiro texto
        if texts:
            print(f"🔍 [DEBUG] Primeiro texto (repr): {repr(texts[0])}", flush=True)
            print(f"🔍 [DEBUG] Espaços no primeiro texto: {texts[0].count(' ')}", flush=True)
            print(f"🔍 [DEBUG] Primeiros 100 chars: {repr(texts[0][:100])}", flush=True)
            print(f"🔍 [DEBUG] Começa com espaço? {texts[0].startswith(' ')}", flush=True)
        
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
                    print(f"✅ [DEBUG] {len(sheet_data)} partitura(s) atualizada(s) com {total_notes} notas no total", flush=True)
                else:
                    print(f"✅ [DEBUG] Partitura atualizada com {len(sheet_data.get('notes', []))} notas", flush=True)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}", flush=True)
        
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
        print(f"✅ [DEBUG] Música {song_id} editada com sucesso!", flush=True)
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
        orders = load_orders()
        song_url = f'/lyrics/{song_id}'
        for date, order in orders.items():
            for item in order.get('itens', []):
                if item.get('url') == song_url:
                    order_date = date
                    break
            if order_date:
                break

    return render_template('lyrics.html', song=song, order_date=order_date)

@app.route('/api/lyrics/<int:song_id>')
def api_lyrics(song_id):
    """Retorna os dados completos da música em JSON (para API)."""
    song = next((s for s in load_songs() if s['id'] == song_id), None)
    if not song:
        return jsonify({'error': 'Música não encontrada'}), 404
    
    return jsonify(song)

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
    print('Cliente conectado')


@socketio.on('disconnect')
def handle_disconnect():
    global socketio_clients_connected
    sid = request.sid
    if sid in socketio_clients_by_sid:
        del socketio_clients_by_sid[sid]
    socketio_clients_connected = len(socketio_clients_by_sid)
    print('Cliente desconectado')


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




# --- FIM ------ #



# Load the order of service from the JSON file
DATA_FILE = 'order_of_service.json'
ORDERS_FILE = 'orders.json'

# Funções auxiliares para o novo sistema de ordens
def load_orders():
    """Carrega todas as ordens do arquivo orders.json"""
    try:
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Erro ao carregar orders.json: {e}")
        return {}

def save_orders(orders):
    """Salva todas as ordens no arquivo orders.json"""
    try:
        with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar orders.json: {e}")
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

# Endpoint para obter a última imagem
@app.route('/last_image', methods=['GET'])
def last_image_endpoint():
    data = load_image_path()  # Carrega o caminho da imagem
    return jsonify({"image_url": data.get("image")}), 200














@app.route('/')
@login_required
def index():
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
    print(f'💾 Estado das letras salvo: Música {state.song_id}, Seção {state.section_index}')
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
    # Obtém a URL da imagem atual
    image_url = get_current_image_path()
    return render_template('img.html', image_url=image_url)

@app.route('/presenter')
def presenter():
    return render_template('presenter.html')

@app.route('/help')
def help():
    return render_template('help.html')

@app.route("/clock", methods=["GET", "POST"])
def clock():
    if request.method == "POST":
        # Handle form data here if needed
        pass

    return render_template("relogio.html")

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
    fotos = [f for f in os.listdir(target) if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and os.path.isfile(os.path.join(target, f))]
    fotos_urls = [f'{prefix}/{foto}' for foto in fotos]
    return jsonify({'fotos': fotos_urls})



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
        if file_ext == '.pdf':
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
    global _display_state_cache
    image_url = data['image_url']
    
    # Atualiza cache imediatamente
    _display_state_cache['data'] = {'url1': image_url, 'url2': ''}
    _display_state_cache['timestamp'] = time.time()
    
    # Envia para clientes primeiro (não espera banco)
    emit('display_image', {'image_url': image_url}, broadcast=True)
    
    # Salva no banco de forma assíncrona
    def save_async():
        with app.app_context():
            state = DisplayState.query.first()
            if not state:
                state = DisplayState(url1=image_url, url2='')
                db.session.add(state)
            else:
                state.url1 = image_url
                state.url2 = ''
            db.session.commit()
    
    threading.Thread(target=save_async, daemon=True).start()

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
        print(f"[show_image_zoom] url={image_url} zoom={zoom} origin={origin} pan={pan}")
    except Exception:
        pass
    if not image_url:
        return
    emit('display_image_zoom', {'image_url': image_url, 'zoom': zoom, 'origin': origin, 'pan': pan}, broadcast=True)

# Evento WebSocket para transmitir duas URLs de imagem
@socketio.on('show_two_urls')
def handle_show_two_urls(data):
    global _display_state_cache
    
    # Atualiza cache imediatamente
    _display_state_cache['data'] = {'url1': data['url1'], 'url2': data['url2']}
    _display_state_cache['timestamp'] = time.time()
    
    # Envia para clientes primeiro (não espera banco)
    emit('display_two_urls', {'url1': data['url1'], 'url2': data['url2']}, broadcast=True)
    
    # Salva no banco de forma assíncrona
    def save_async():
        with app.app_context():
            state = DisplayState.query.first()
            if not state:
                state = DisplayState(url1=data['url1'], url2=data['url2'])
                db.session.add(state)
            else:
                state.url1 = data['url1']
                state.url2 = data['url2']
            db.session.commit()
    
    threading.Thread(target=save_async, daemon=True).start()

# Evento WebSocket para transmitir a URL
@socketio.on('send_url')
def handle_send_url(url):
    emit('update_url', {'url': url}, broadcast=True)

# Evento WebSocket para transmitir letras de músicas
@socketio.on('update_lyrics')
def handle_update_lyrics(data):
    print(f'📨 Recebido update_lyrics: {data.get("title", "Sem título")}')
    emit('update_lyrics', data, broadcast=True)

# Evento WebSocket para mudança de seção
@socketio.on('section_changed')
def handle_section_changed(data):
    print(f'📨 Recebido section_changed: Song {data.get("songId")}, Section {data.get("sectionIndex")}')
    emit('section_changed', data, broadcast=True)

# Evento WebSocket para mostrar/esconder letras
@socketio.on('toggle_lyrics_visibility')
def handle_toggle_lyrics_visibility(data):
    visible = data.get('visible', True)
    print(f'👁️ Toggle letras: {"Mostrar" if visible else "Esconder"}')
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
    print(f"🔗 Serviço mDNS registrado: http://ucontrol.local:{PORTA}")



# === Rota de teste ===
@app.route('/')
def home():
    return "Servidor Flask com mDNS ativo!"


# === Iniciar Flask ===
def run_flask():
    socketio.run(app, host="0.0.0.0", port=PORTA, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
        

# === Abrir navegador ===
def open_browser():
    time.sleep(3)  # Dá tempo do servidor iniciar
    webbrowser.open(f"http://127.0.0.1:{PORTA}/")


# === Execução principal ===
if __name__ == '__main__':
    print(f"✅ Acesse localmente: http://127.0.0.1:{PORTA}/")
    print(f"🌐 Ou via mDNS: http://{MDNS_DOMINIO}:{PORTA}/")
    
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
        print("\n🛑 Servidor interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro no servidor: {e}")