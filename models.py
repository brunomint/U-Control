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


# Histórico do que foi exibido (bíblia, imagem, vídeo, música, ticker) —
# substitui display_log.json. INSERT-only: era leitura+append+reescrita do
# arquivo inteiro a cada evento, agora é um INSERT real por evento.
class DisplayLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # image | bible | song | ticker
    title = db.Column(db.String(500), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    ts = db.Column(db.DateTime, nullable=False, index=True)


# Configurações persistidas (tradução da bíblia, tema claro/escuro do
# display) — substitui settings.json. Linha única, mesmo padrão
# `Model.query.first()` de DisplayState/LyricsState.
class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bible_translation = db.Column(db.String(20), nullable=True)
    display_bg_dark = db.Column(db.Boolean, nullable=True, default=False)


# Rótulo salvo da última contagem regressiva — substitui countdown_config.json.
class CountdownConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(200), nullable=True)


# Texto salvo do ticker de avisos — substitui ticker_config.json.
class TickerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=True)


# Último caminho de imagem da galeria mostrado — substitui image_paths.json.
# Já bastante redundante com DisplayState (é só um fallback de 3º nível em
# /last_image), mantido por completude.
class ImagePath(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(500), nullable=True)


# URLs salvas manualmente pelo operador em control.html — substitui
# urls.json. Recurso de "favoritos", separado do DisplayState (sync ao vivo).
class SavedUrls(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url1 = db.Column(db.String(500), nullable=True)
    url2 = db.Column(db.String(500), nullable=True)
    url3 = db.Column(db.String(500), nullable=True)
