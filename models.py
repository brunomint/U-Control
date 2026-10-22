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
    # JSON exato do último payload update_lyrics (title/type/text/sheets/
    # sheetData/theme) — display_state._last_lyrics_payload é só em
    # memória e some a cada restart do servidor; api_current_display usa
    # isto como fallback pra reconstruir a EXATA última tela (inclusive
    # partitura) em vez de tentar remontar a partir de song_id+
    # section_index (perdia o tipo mixed/sheet, sempre virava texto puro
    # com o marcador 🎼 PARTITURA_INTEGRADA_... cru — bug real encontrado
    # nesta sessão).
    last_payload = db.Column(db.Text, nullable=True)
    # Estado do botão "Esconder"/"Mostrar" (toggle_lyrics_visibility) — antes
    # só existia como variável local no JS do operador, sempre assumindo
    # `true` a cada carregamento de /lyrics/<id>, sem relação com o que a
    # tela pública estava mostrando de verdade. Persistido aqui pra virar
    # fonte única de verdade (main.py/blueprints/lyrics.py lê isto pra
    # inicializar o botão com o estado real).
    visible = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


# Conteúdo "preparado" mas ainda não liberado pro ar — um registro por
# TIPO (kind), não um slot único: preparar uma foto no /presenter não
# deve apagar silenciosamente uma letra que outro operador preparou em
# /lyrics/<id> segundos antes (são papéis/pessoas diferentes na
# prática). Nunca representa o que está no ar de verdade — isso
# continua sendo DisplayState/LyricsState, escritos só no momento da
# liberação (release_staged_content reusa os handlers reais de
# update_lyrics/update_bible/show_image, não duplica a lógica deles).
# Ver plano "preparar vs. liberar" — achado num incidente ao vivo
# (2026-08-16) onde clicar em /lyrics/<id> ou /bible/control mudava a
# tela pública sem passar pelo /control.
class StagedContent(db.Model):
    kind = db.Column(db.String(20), primary_key=True)  # 'lyrics' | 'bible' | 'image'
    payload = db.Column(db.JSON, nullable=False)  # mesmo formato que update_lyrics/update_bible/show_image já esperam
    label = db.Column(db.String(300), nullable=True)  # preview curto pro painel do /control
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
    # Segunda versão mostrada junto no telão ('' / None = só uma)
    bible_translation_2 = db.Column(db.String(20), nullable=True)
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
    # Nome que aparece no botão da fonte no Controle ("Câmera", "Slides")
    name1 = db.Column(db.String(80), nullable=True)
    name2 = db.Column(db.String(80), nullable=True)
    name3 = db.Column(db.String(80), nullable=True)
