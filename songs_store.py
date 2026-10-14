"""Acesso às músicas — tabelas Song/SongSection/SheetData (models_songs.py),
substituindo songs.json. Usado pelo blueprint de songs (CRUD) e também
pela área de letras em blueprints/lyrics.py/display.py e por /view/<song_id>,
por isso vive num módulo à parte em vez de dentro do blueprint.

load_songs()/save_songs() mantêm exatamente o mesmo formato de antes —
lista de dicts, no mesmo formato que songs.json produzia (chaves opcionais
omitidas quando o valor é None, igual o código original fazia com `del`) —
com uma exceção deliberada: cada item de `sheet_data` agora sempre inclui
todas as chaves do formato canônico (`id, clef, keySig, timeSig, measures,
ties, chords`), mesmo quando None (ver `_normalize_sheet`). É a Fase 1 da
unificação de renderização VexFlow (.claude/plans/harmonic-mixing-breeze.md)
— antes havia duas versões ligeiramente diferentes dessa lógica
(_normalize_sheet vs. o loop inline em _song_to_dict), fonte de bugs.

save_songs(songs) faz um sync completo por id, mas com DIFF real: cada
chamador sempre recarrega a lista inteira, muda uma música, e chama save
com a lista inteira de novo (mesmo padrão de sempre) — só que
/lyrics/<id> faz isso em TODA visita de página só pra atualizar
last_played. Um "apaga tudo e reinsere" ingênuo reescreveria as seções e
partituras das 381 músicas a cada visita de letra durante um culto ao
vivo. Por isso: colunas escalares (title/author/video_url/audio_url/
theme/last_played) são sempre atribuídas — o SQLAlchemy já não gera
UPDATE se o valor não mudou — mas as listas-filhas (sections/sheet_data)
só são recriadas quando o conteúdo comparado realmente difere do que já
está no banco."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from extensions import db
from models_songs import SheetData, Song, SongSection


def _sections_to_dicts(sections):
    return [{'title': s.title, 'text': s.text} for s in sections]


def _normalize_sheet(sh):
    """Formato canônico único (chave wire, usado em toda parte — payload
    do editor, sheet_data embutido no dict da música, coluna do banco):
    {id, clef, keySig, timeSig, measures, ties, chords}. Ver plano em
    .claude/plans/harmonic-mixing-breeze.md — unificação de renderização
    VexFlow.

    `measures`/`timeSig` aceitam as chaves antigas (`notes`/`time_signature`)
    como fallback — transitório, até a Fase 7 do plano acima atualizar
    new_song.js/edit_song.js pra mandar o formato novo. O valor antigo
    (array achatado, não aninhado por compasso) é gravado como veio, sem
    tentar reagrupar aqui — a detecção formato-antigo-vs-novo já é
    responsabilidade do renderizador compartilhado (Fase 3+), não deste
    módulo, e serve tanto pra dado gravado antes da Fase 1 quanto pra
    dado gravado nessa janela de transição."""
    return {
        'id': sh.get('id'),
        'clef': sh.get('clef'),
        'keySig': sh.get('keySig'),
        'timeSig': sh.get('timeSig') or sh.get('time_signature'),
        'measures': sh.get('measures') if sh.get('measures') is not None else sh.get('notes'),
        'ties': sh.get('ties'),
        'chords': sh.get('chords'),
    }


def _sheet_model_to_dict(sd):
    return _normalize_sheet({
        'id': sd.client_id,
        'clef': sd.clef,
        'keySig': sd.key_sig,
        'timeSig': sd.time_signature,
        'measures': sd.measures,
        'ties': sd.ties,
        'chords': sd.chords,
    })


def _sheets_to_dicts(sheet_data):
    return [_sheet_model_to_dict(sd) for sd in sheet_data]


def _song_to_dict(song):
    d = {'id': song.id, 'title': song.title, 'author': song.author}
    if song.video_url is not None:
        d['video_url'] = song.video_url
    if song.audio_url is not None:
        d['audio_url'] = song.audio_url
    if song.theme is not None:
        d['theme'] = song.theme
    if song.last_played is not None:
        d['last_played'] = song.last_played.isoformat()
    d['sections'] = _sections_to_dicts(song.sections)
    if song.sheet_data:
        d['sheet_data'] = _sheets_to_dicts(song.sheet_data)
    return d


def load_songs():
    """Carrega as músicas."""
    # selectinload em vez do lazy-load padrão: sem isso, cada acesso a
    # song.sections/song.sheet_data dentro de _song_to_dict dispara uma
    # query SEPARADA por música — 371 músicas reais viravam 743 queries
    # (1 + 371 + 371), ~3.4s só pra carregar. selectinload busca todas as
    # seções e todas as partituras em 2 queries únicas (WHERE song_id IN
    # (...)), independente de quantas músicas existam. Achado ao investigar
    # por que salvar uma música editada no Pi demorava ~7s no total (achado
    # real, não latência de rede — 2026-08-15).
    songs = Song.query.options(
        selectinload(Song.sections), selectinload(Song.sheet_data)
    ).order_by(Song.id.asc()).all()
    return [_song_to_dict(s) for s in songs]


def get_song(song_id):
    """Carrega UMA música só, com as mesmas relações eager-loaded acima —
    usado por /lyrics/<id>, que antes chamava load_songs() (as 371) só
    pra achar 1 pelo id. Retorna None se não existir.

    db.session.get(..., options=[...]) em vez de Query.get() encadeado
    com .options(): Session.get() confere primeiro o identity map, e só
    o parâmetro options garante que o eager load seja aplicado mesmo se
    o objeto já estiver na sessão (e portanto os selectinload de um
    .options() encadeado seriam ignorados nesse caso)."""
    song = db.session.get(
        Song, song_id,
        options=[selectinload(Song.sections), selectinload(Song.sheet_data)],
    )
    return _song_to_dict(song) if song else None


def touch_last_played(song_id):
    """Atualiza só o last_played de uma música — 1 UPDATE, sem tocar nas
    outras 370. /lyrics/<id> chamava load_songs()+save_songs() com a
    LISTA INTEIRA (371 músicas) a cada visita só pra isso: mesmo já
    reduzido de 743 pra 3 queries (ver load_songs()), ainda era ~2.3s de
    trabalho proporcional ao total de músicas — pra atualizar 1 coluna
    de 1 linha. Achado a partir do relato real "cifras ficam lentas
    quando troca de música" (2026-08-15)."""
    song = db.session.get(Song, song_id)
    if song:
        song.last_played = datetime.now()
        db.session.commit()


def set_theme(song_id, theme):
    """Atualiza só o theme de uma música — mesma ideia de
    touch_last_played(), pro endpoint /api/lyrics/<id>/theme que também
    fazia load_songs()+save_songs() da lista inteira. Retorna False se a
    música não existir."""
    song = db.session.get(Song, song_id)
    if not song:
        return False
    song.theme = theme
    db.session.commit()
    return True


def _apply_song_fields(song, data, is_new):
    song.title = data.get('title')
    song.author = data.get('author')
    song.video_url = data.get('video_url')
    song.audio_url = data.get('audio_url')
    song.theme = data.get('theme')
    last_played = data.get('last_played')
    song.last_played = datetime.fromisoformat(last_played) if last_played else None

    incoming_sections = data.get('sections') or []
    if is_new or incoming_sections != _sections_to_dicts(song.sections):
        song.sections = [
            SongSection(position=i, title=sec.get('title'), text=sec.get('text'))
            for i, sec in enumerate(incoming_sections)
        ]

    incoming_sheets = [_normalize_sheet(sh) for sh in (data.get('sheet_data') or [])]
    if is_new or incoming_sheets != _sheets_to_dicts(song.sheet_data):
        song.sheet_data = [
            SheetData(
                client_id=sh.get('id'),
                measures=sh.get('measures'),
                ties=sh.get('ties'),
                time_signature=sh.get('timeSig'),
                clef=sh.get('clef'),
                key_sig=sh.get('keySig'),
                chords=sh.get('chords'),
            )
            for sh in incoming_sheets
        ]


def save_songs(songs):
    """Salva as músicas (sync completo por id, com diff — ver docstring do
    módulo)."""
    incoming_ids = {s['id'] for s in songs}
    # Mesmo motivo do selectinload em load_songs() acima — _apply_song_fields
    # também compara song.sections/song.sheet_data pra decidir se recria as
    # listas-filhas, e sem eager loading isso é outra rodada de N+1 queries.
    existing = {
        s.id: s for s in Song.query.options(
            selectinload(Song.sections), selectinload(Song.sheet_data)
        ).all()
    }

    for song_id, song in existing.items():
        if song_id not in incoming_ids:
            db.session.delete(song)

    for data in songs:
        song = existing.get(data['id'])
        if song is None:
            song = Song(id=data['id'])
            db.session.add(song)
            _apply_song_fields(song, data, is_new=True)
        else:
            _apply_song_fields(song, data, is_new=False)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


def save_song(data):
    """Grava UMA música (cria se o id não existir) — mesma regra de diff do
    save_songs(), mas sem carregar e comparar as outras ~390. Editar,
    criar e salvar partitura chamavam load_songs()+save_songs() com a
    lista inteira: ~2 s de CPU no Pi a cada Salvar, com o servidor (1
    worker) parado nesse tempo pra todo mundo — telão e monitor inclusive
    (medido em 2026-10-14)."""
    song = db.session.get(
        Song, data['id'],
        options=[selectinload(Song.sections), selectinload(Song.sheet_data)],
    )
    is_new = song is None
    if is_new:
        song = Song(id=data['id'])
        db.session.add(song)
    _apply_song_fields(song, data, is_new=is_new)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()


def delete_song(song_id):
    """Exclui UMA música (seções e partituras vão junto pelo cascade)."""
    song = db.session.get(Song, song_id)
    if song:
        db.session.delete(song)
        db.session.commit()


def next_song_id():
    """Próximo id livre, direto no banco (sem carregar as músicas)."""
    return (db.session.query(func.max(Song.id)).scalar() or 0) + 1


def get_next_id(songs):
    """Obtém o próximo ID disponível para uma nova música."""
    return max((song['id'] for song in songs), default=0) + 1
