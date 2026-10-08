"""Login, registro, dashboard e gestão de usuários. Único blueprint deste
piloto cujos endpoints são referenciados por nome em outros lugares
(main.py, extensions.py e templates) — todos atualizados pro prefixo
`auth.` nesta mesma leva."""
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from display_log import load_display_log
from extensions import db, login_manager
from models import User

auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Rate limiting de tentativas de login (em memória, reinicia a cada boot —
# suficiente para o modelo de ameaça doméstico/rede local, não precisa
# persistir). Mesmo padrão usado no projeto fileswift.
tentativas_login_por_ip = defaultdict(list)
LOGIN_MAX_TENTATIVAS = 5
LOGIN_JANELA = timedelta(minutes=10)


def _obter_ip_cliente(req):
    ip_cliente = req.environ.get('HTTP_X_FORWARDED_FOR', req.environ.get('REMOTE_ADDR', 'unknown'))
    if ',' in ip_cliente:
        ip_cliente = ip_cliente.split(',')[0].strip()
    return ip_cliente


def _ip_esta_bloqueado(ip):
    agora = datetime.now()
    tentativas = [t for t in tentativas_login_por_ip.get(ip, []) if agora - t < LOGIN_JANELA]
    tentativas_login_por_ip[ip] = tentativas
    return len(tentativas) >= LOGIN_MAX_TENTATIVAS


def _registrar_tentativa_falha(ip):
    tentativas_login_por_ip[ip].append(datetime.now())


def _limpar_tentativas(ip):
    tentativas_login_por_ip.pop(ip, None)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip_cliente = _obter_ip_cliente(request)

        if _ip_esta_bloqueado(ip_cliente):
            flash('Muitas tentativas seguidas. Aguarde alguns minutos e tente de novo.')
            return redirect(url_for('auth.login'))

        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            _limpar_tentativas(ip_cliente)
            login_user(user)
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('auth.dashboard'))
        else:
            _registrar_tentativa_falha(ip_cliente)
            flash('Usuário ou senha incorretos.')
    return render_template('login.html')


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    log = load_display_log()

    # 3 músicas tocadas mais recentemente (únicas, do display_log)
    seen, recent_songs = set(), []
    for entry in reversed(log):
        if entry.get('type') == 'song' and entry.get('title') not in seen:
            seen.add(entry['title'])
            recent_songs.append(entry)
            if len(recent_songs) >= 3:
                break

    return render_template('dashboard.html', recent_songs=recent_songs,
                           recent_activity=group_activity(log),
                           today=datetime.now().strftime('%Y-%m-%d'))


# Rotas fixas que aparecem como "título" no log quando o telão troca de
# tela (display.py loga a URL crua) — nomes que o operador reconhece.
_ROUTE_NAMES = {
    '/lyrics/display': 'Cifra',
    '/lyrics/display/public': 'Letra',
    '/clock': 'Relógio',
    '/img': 'Imagem',
    '/bible/display': 'Bíblia',
    '/countdown': 'Cronômetro',
}


def _describe_activity(entry):
    """(ação, alvo) legíveis pra uma entrada do display_log."""
    kind, title = entry.get('type'), (entry.get('title') or '').strip()
    if kind == 'song':
        return 'Exibiu a letra de', title
    if kind == 'bible':
        return 'Exibiu', title
    if kind == 'ticker':
        return 'Aviso no telão:', title
    if title.startswith('/static/'):
        from urllib.parse import unquote
        return 'Exibiu a imagem', unquote(title.rsplit('/', 1)[-1])
    parts = [_ROUTE_NAMES.get(p.strip(), p.strip()) for p in title.split(' + ')]
    return 'Telão mudou para', ' + '.join(parts)


def group_activity(log, limit=5):
    """Últimas `limit` atividades, juntando repetições seguidas da mesma
    coisa (ex. a mesma música exibida 5 vezes em 3 minutos vira uma linha
    "×5" com o intervalo de horário)."""
    groups = []
    for entry in reversed(log):
        key = (entry.get('type'), entry.get('title'))
        if groups and groups[-1]['key'] == key:
            groups[-1]['count'] += 1
            groups[-1]['first_ts'] = entry.get('ts', '')
            continue
        if len(groups) >= limit:
            break
        action, target = _describe_activity(entry)
        groups.append({
            'key': key, 'type': entry.get('type'), 'action': action, 'target': target,
            'count': 1, 'last_ts': entry.get('ts', ''), 'first_ts': entry.get('ts', ''),
        })
    return groups


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # Limpa qualquer dado da sessão
    return redirect(url_for('auth.login'))


@auth_bp.route('/usuarios')
@login_required
def visualizar_usuarios():
    # Buscar todos os usuários no banco de dados
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)


@auth_bp.route('/remover_usuario/<int:id>', methods=['POST'])
@login_required
def remover_usuario(id):
    usuario = User.query.get(id)
    if usuario:
        db.session.delete(usuario)
        db.session.commit()
        flash('Usuário removido com sucesso.')
    else:
        flash('Usuário não encontrado.', 'error')
    return redirect(url_for('auth.visualizar_usuarios'))


@auth_bp.route('/alterar_senha/<int:id>', methods=['POST'])
@login_required
def alterar_senha(id):
    usuario = User.query.get(id)
    password = request.form.get('password', '')
    if not usuario:
        flash('Usuário não encontrado.', 'error')
    elif not password:
        flash('A senha não pode estar em branco.', 'error')
    else:
        usuario.password = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.commit()
        flash(f'Senha de "{usuario.username}" alterada com sucesso!')
    return redirect(url_for('auth.visualizar_usuarios'))


@auth_bp.route('/adicionar_usuario', methods=['POST'])
@login_required
def adicionar_usuario():
    username = request.form['username']
    password = request.form['password']

    # Verifica se o nome de usuário já existe
    if User.query.filter_by(username=username).first():
        flash('Já existe um usuário com esse nome.', 'error')
    else:
        # Criptografa a senha
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Usuário adicionado com sucesso!')

    return redirect(url_for('auth.visualizar_usuarios'))
