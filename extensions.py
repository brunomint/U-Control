"""Instâncias de extensão Flask, sem app vinculado ainda (padrão factory:
`.init_app(app)` acontece dentro de `create_app()`, em main.py). Módulo
independente — não importa de main.py nem de blueprints/, pra nunca criar
import circular conforme mais blueprints forem extraídos."""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'login'

socketio = SocketIO()
