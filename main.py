from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
)
from werkzeug.routing import BaseConverter
from flask_login import login_required
import os
import json
import threading
import time
import webbrowser
import socket
import qrcode
from zeroconf import ServiceInfo, Zeroconf
import logging
from logging.handlers import RotatingFileHandler

from extensions import db, migrate, login_manager, socketio
import models_songs  # noqa: F401 — importado só pra registrar as tabelas em db.metadata
import models_orders  # noqa: F401 — idem
from blueprints.countdown import countdown_bp, init_countdown_state
from blueprints.ticker import ticker_bp, init_ticker_state
from blueprints.auth import auth_bp
from blueprints.bible import bible_bp, generate_bible_url
from blueprints.cifras import cifras_bp
from songs_store import load_songs
from blueprints.songs import songs_bp
from network_utils import PORTA, obter_endereco_ip
from blueprints.utils import utils_bp
from blueprints.gallery import gallery_bp
from orders_store import load_orders
from blueprints.orders import orders_bp
from blueprints.agenda import agenda_bp
import blueprints.screen_share  # noqa: F401 — importado só pelo efeito colateral de registrar os handlers de socket
from blueprints.lyrics import lyrics_bp
from blueprints.display import display_bp

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
    do módulo. Se config vier, sobrescreve os defaults (usado pelos testes)."""
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

    with app.app_context():
        if app.config.get('TESTING'):
            # Banco em memória dos testes: recriado do zero a cada processo,
            # não faz sentido versionar com migration. Fora de teste (dev ou
            # produção), o schema vem só de `flask db upgrade` (migrations/).
            db.create_all()

        # Hidrata o rótulo/texto salvos (countdown/ticker) do banco pro
        # estado em memória — precisa rodar aqui (depois de db.init_app(),
        # dentro de app_context), não no import do módulo como antes.
        init_countdown_state()
        init_ticker_state()

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
    app.register_blueprint(lyrics_bp)
    app.register_blueprint(display_bp)

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


@app.route('/')
@login_required
def index():
    return redirect(url_for('auth.dashboard'))

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