"""Busca de músicas (título, autor ou letra) sem carregar o banco inteiro a
cada letra digitada.

/search (Controle, ordem do culto, agenda) e /api/songs/search (cifras)
carregavam as músicas todas — com seções e partituras — a cada pesquisa, e
/search ainda devolvia as músicas inteiras: com 1.062 músicas, buscar "S"
levava 3,5 s e 1,8 MB no Pi (24/11/2026), e a busca roda a cada tecla.

Aqui fica um índice leve em memória (id, título, autor e a letra em texto,
sem acento e em minúsculas), montado com duas consultas simples. Qualquer
gravação ou exclusão de música/seção (editor, importação, backup) invalida o
índice pelos eventos do SQLAlchemy; por segurança ele também se refaz a cada
5 minutos. O servidor roda num processo só (gunicorn 1 worker), então o
índice em memória é o mesmo para todos."""
import threading
import time
import unicodedata

from sqlalchemy import event

_VALIDADE_S = 300
_trava = threading.Lock()
_indice = None          # [(id, titulo, autor, titulo_n, autor_n, letra_n)]
_feito_em = 0.0


def normalizar(texto):
    """Minúsculas e sem acento: "Graça" e "graca" batem."""
    texto = unicodedata.normalize('NFKD', str(texto or '').lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def invalidar(*_args, **_kwargs):
    global _indice
    _indice = None


def _montar():
    from extensions import db
    from models_songs import Song, SongSection
    musicas = db.session.query(Song.id, Song.title, Song.author).all()
    letras = {}
    for song_id, texto in db.session.query(SongSection.song_id, SongSection.text):
        partes = texto if isinstance(texto, list) else [texto]
        letras.setdefault(song_id, []).append('\n'.join(str(p or '') for p in partes))
    return [(i, t or '', a or '', normalizar(t), normalizar(a), normalizar('\n'.join(letras.get(i, []))))
            for i, t, a in musicas]


def _indice_atual():
    global _indice, _feito_em
    with _trava:
        if _indice is None or time.monotonic() - _feito_em > _VALIDADE_S:
            _indice = _montar()
            _feito_em = time.monotonic()
        return _indice


def buscar(consulta, limite=50):
    """[{'id', 'title', 'author'}]: primeiro as que começam pelo título, depois
    as que têm no título, no autor e, por fim, na letra (cada grupo em ordem
    alfabética)."""
    q = normalizar(consulta).strip()
    if not q:
        return []
    grupos = ([], [], [], [])
    for item in _indice_atual():
        i, titulo, autor, titulo_n, autor_n, letra_n = item
        if titulo_n.startswith(q):
            grupos[0].append(item)
        elif q in titulo_n:
            grupos[1].append(item)
        elif q in autor_n:
            grupos[2].append(item)
        elif q in letra_n:
            grupos[3].append(item)
    saida = []
    for grupo in grupos:
        for i, titulo, autor, titulo_n, *_ in sorted(grupo, key=lambda x: x[3]):
            saida.append({'id': i, 'title': titulo, 'author': autor})
            if len(saida) >= limite:
                return saida
    return saida


def ligar_eventos():
    """Gravou ou apagou música/seção: o índice é refeito na próxima busca."""
    from models_songs import Song, SongSection
    for modelo in (Song, SongSection):
        for nome in ('after_insert', 'after_update', 'after_delete'):
            if not event.contains(modelo, nome, invalidar):
                event.listen(modelo, nome, invalidar)
