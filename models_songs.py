"""Modelos de música (letras/cifras), substituindo songs.json. O `id` de
Song é preservado do JSON original na importação (Fase 5.4) — não é
reatribuído — porque é referenciado em URLs (`/lyrics/<id>`, `/edit_song/<id>`)
e QR codes. SheetData usa PK própria (surrogate autoincrement): o id estilo
timestamp do JSON original é só uma chave de elemento DOM local à página,
nunca uma referência externa, então vira `client_id` (não-único) em vez de
PK, evitando risco de colisão sem necessidade nenhuma."""
from extensions import db


class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(300), nullable=False)
    video_url = db.Column(db.String(500), nullable=True)
    audio_url = db.Column(db.String(500), nullable=True)
    theme = db.Column(db.JSON, nullable=True)
    last_played = db.Column(db.DateTime, nullable=True)

    sections = db.relationship(
        'SongSection', backref='song', order_by='SongSection.position',
        cascade='all, delete-orphan',
    )
    sheet_data = db.relationship(
        'SheetData', backref='song', order_by='SheetData.id',
        cascade='all, delete-orphan',
    )


class SongSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), nullable=True)
    # Lista com o(s) parágrafo(s) da seção — hoje sempre 1 elemento em todos
    # os dados reais, mas guardado como veio do JSON (não achatado pra
    # string) pra não presumir que isso sempre vale.
    text = db.Column(db.JSON, nullable=False)


class SheetData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    client_id = db.Column(db.BigInteger, nullable=True)
    time_signature = db.Column(db.String(20), nullable=True)
    clef = db.Column(db.String(20), nullable=True)
    key_sig = db.Column(db.String(20), nullable=True)
    measures = db.Column(db.JSON, nullable=False)
    ties = db.Column(db.JSON, nullable=True)
    chords = db.Column(db.JSON, nullable=True)
