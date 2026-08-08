"""Login, registro, dashboard e gestão de usuários. Único blueprint deste
piloto cujos endpoints são referenciados por nome em outros lugares
(main.py, extensions.py e templates) — todos atualizados pro prefixo
`auth.` nesta mesma leva."""
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


@auth_bp.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('auth.dashboard'))
        else:
            flash('Usuário ou senha incorretos.')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
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
            return redirect(url_for('auth.login'))
    return render_template('register.html')


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

    # 5 entradas mais recentes de atividade
    recent_activity = list(reversed(log[-5:])) if log else []

    return render_template('dashboard.html', recent_songs=recent_songs, recent_activity=recent_activity)


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
        flash('Usuário não encontrado.')
    return redirect(url_for('auth.visualizar_usuarios'))


@auth_bp.route('/adicionar_usuario', methods=['POST'])
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

    return redirect(url_for('auth.visualizar_usuarios'))
