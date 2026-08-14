"""Instâncias de extensão Flask, sem app vinculado ainda (padrão factory:
`.init_app(app)` acontece dentro de `create_app()`, em main.py). Módulo
independente — não importa de main.py nem de blueprints/, pra nunca criar
import circular conforme mais blueprints forem extraídos."""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

socketio = SocketIO()

csrf = CSRFProtect()


# gunicorn.conf.py roda workers=1/threads=16 — até 16 threads reais podem
# bater no SQLite ao mesmo tempo. Sem isso, um writer concorrente recebe
# "database is locked" na hora em vez de esperar. Sem efeito em bancos
# ':memory:' (usados nos testes) — SQLite ignora WAL nesse caso.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
