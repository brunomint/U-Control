from flask_login import UserMixin

from extensions import db


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
    media_type = db.Column(db.String(10), nullable=True, default='image')  # 'image' ou 'video'
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


# Modelo para persistir estado das letras (música + seção)
class LyricsState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, nullable=True)  # ID da música atual
    section_index = db.Column(db.Integer, default=0)  # Índice da seção atual
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
