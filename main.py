from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
)
from werkzeug.routing import BaseConverter
from flask_login import current_user, login_required
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

from extensions import db, migrate, login_manager, socketio, csrf
import models_songs  # noqa: F401 — importado só pra registrar as tabelas em db.metadata
import models_orders  # noqa: F401 — idem
from blueprints.countdown import countdown_bp, init_countdown_state
from blueprints.ticker import ticker_bp, init_ticker_state
from blueprints.auth import auth_bp
from blueprints.bible import bible_bp, generate_bible_url
from blueprints.cifras import cifras_bp
from songs_store import get_song
from blueprints.songs import songs_bp
from network_utils import PORTA, obter_endereco_ip
from blueprints.utils import utils_bp
from blueprints.gallery import gallery_bp
from orders_store import get_order, load_orders
from blueprints.orders import orders_bp
from blueprints.agenda import agenda_bp
import blueprints.screen_share  # noqa: F401 — importado só pelo efeito colateral de registrar os handlers de socket
from blueprints.lyrics import lyrics_bp
from blueprints.display import display_bp
from nav_config import grouped_nav_items, items_for_context, qr_endpoints

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
        # WTF_CSRF_ENABLED=False só nos testes: o test client do Flask não é
        # um navegador de verdade, então não tem como carregar um token da
        # página antes de cada POST — exigir CSRF ali só quebraria a suíte
        # sem testar nada de real. Em produção/dev normal fica sempre True.
        config = {'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'TESTING': True, 'WTF_CSRF_ENABLED': False}
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
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

    def _versioned_static(filename):
        # ?v=<mtime> força o navegador a buscar a versão nova sempre que o
        # arquivo muda, sem precisar de hard-refresh manual — esses scripts
        # são JS clássico (sem hash de build) e o Cache-Control:no-cache
        # padrão do Flask nem sempre é revalidado numa aba já aberta.
        path = os.path.join(app.static_folder, filename)
        try:
            v = int(os.path.getmtime(path))
        except OSError:
            v = 0
        return url_for('static', filename=filename) + f'?v={v}'

    app.jinja_env.globals['versioned_static'] = _versioned_static

    @app.context_processor
    def inject_nav():
        # Disponível em todo template sem precisar passar manualmente em
        # cada render_template — ver .claude/plans/harmonic-mixing-breeze.md.
        # current_user.is_authenticated funciona também fora de rota
        # @login_required (visitante deslogado só não vê os itens com
        # login_required=True). launcher_items alimenta o submenu
        # "Links" do sidebar de control.html (telas que o operador abre
        # em nova aba mantendo o painel aberto).
        logged_in = current_user.is_authenticated
        return {
            'nav_groups': grouped_nav_items(logged_in),
            'launcher_items': items_for_context('launcher', logged_in),
        }

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

# Geração de QR Codes fica pro fim do arquivo (depois de "/view" e "/"
# serem registradas) — nav_config.qr_endpoints() inclui view_song_order,
# que só existe no url_map depois dessas rotas serem definidas mais
# abaixo neste mesmo arquivo.


@app.route('/view')
def view_song_order():
    order_date = request.args.get('order')
    return render_template('view_song_order.html', order_date=order_date)

# Rota para visualizar ordem de culto por data (compartilhável)
@app.route('/view/order/<date>')
def view_order_by_date(date):
    """Visualiza uma ordem de culto específica por data"""
    order = get_order(date)
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
    song = get_song(song_id)
    if not song:
        return "Música não encontrada!", 404

    # Verifica se há parâmetro de data na URL
    order_date = request.args.get('order')
    bible_items = []
    order_data = []

    if order_date:
        # Carrega ordem específica por data — get_order() em vez de
        # load_orders().get(...): esse é o caso mais comum (a URL já vem
        # com ?order=<data> na maioria das navegações reais), não precisa
        # carregar as 176 ordens só pra achar 1 (mesma causa raiz do
        # achado em touch_last_played(), ver songs_store.py — 2026-08-15).
        order_data = get_order(order_date).get('itens', [])
    else:
        # Busca a ordem que contém esta música — aqui sim precisa das 176
        # (não dá pra saber qual data tem a música sem olhar todas).
        orders = load_orders()
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
        
        # Fallback: nenhuma ordem encontrada pra essa música, usa a ordem de
        # hoje (antes lia order_of_service.json, um bucket solto sem data
        # — Fase 5.6, unificado na mesma tabela Order das demais ordens)
        if not order_data:
            from datetime import date as _date_cls
            today = _date_cls.today().isoformat()
            order_data = orders.get(today, {}).get('itens', [])
    
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

# Gerar os QR Codes — aqui, não antes, porque nav_config.qr_endpoints()
# inclui rotas definidas neste mesmo arquivo (ex. view_song_order) que só
# existem no url_map depois de todas as rotas acima serem registradas.
with app.test_request_context():
    # url_for precisa de um contexto de requisição pra montar caminhos
    # relativos fora de uma requisição de verdade — app_context sozinho
    # não basta (RuntimeError: "Unable to build URLs outside an active
    # request without 'SERVER_NAME' configured").
    _qr_rotas = [url_for(_endpoint).lstrip('/') for _endpoint in qr_endpoints()]
gerar_qrcodes(_qr_rotas)

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