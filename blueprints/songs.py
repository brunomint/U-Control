"""CRUD de músicas, editor de partitura e busca. As páginas /view/* (que
cruzam songs+orders+bíblia) e a área de letras (lyrics/*) ficam de fora,
em main.py — usam songs_store diretamente."""
import json
import logging
import time

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from songs_store import get_next_id, load_songs, save_songs

logger = logging.getLogger('ucontrol')

songs_bp = Blueprint('songs', __name__)


def _count_notes(sheet):
    """Conta notas de um dict de partitura, só pra log de debug — aceita
    o formato canônico (measures aninhado) e o antigo (notes achatado,
    de antes da Fase 1 da unificação de renderização VexFlow)."""
    measures = sheet.get('measures')
    if isinstance(measures, list):
        return sum(len(m) if isinstance(m, list) else 1 for m in measures)
    return len(sheet.get('notes') or [])


# --- Rotas principais editor---

@songs_bp.route('/songs')
@login_required
def list_songs():
    """Lista todas as músicas."""
    return render_template('list_songs.html', songs=load_songs())

@songs_bp.route('/new_song')
@login_required
def new_song():
    """Exibe o formulário para criar uma nova música."""
    return render_template('new_song.html')

@songs_bp.route('/sheet_editor')
@login_required
def sheet_editor():
    """Exibe o editor de partitura VexFlow."""
    return render_template('sheet_editor.html')

@songs_bp.route('/sheet_editor/<int:song_id>')
@login_required
def edit_sheet(song_id):
    """Edita a partitura de uma música específica."""
    songs = load_songs()
    song = next((s for s in songs if s['id'] == song_id), None)
    if not song:
        flash('Música não encontrada!', 'error')
        return redirect(url_for('songs.list_songs'))
    return render_template('sheet_editor.html', song=song)

@songs_bp.route('/api/save_sheet/<int:song_id>', methods=['POST'])
@login_required
def save_sheet_data(song_id):
    """Salva (cria ou atualiza) uma partitura dentro de sheet_data —
    endereça por `id` em vez de sobrescrever a lista inteira, já que uma
    música pode ter mais de uma partitura embutida (bug corrigido na
    Fase 2 do plano de unificação de renderização VexFlow)."""
    try:
        incoming = request.get_json()
        songs = load_songs()

        song = next((s for s in songs if s['id'] == song_id), None)
        if not song:
            return jsonify({"error": "Música não encontrada"}), 404

        sheets = song.get('sheet_data') or []
        sheet_id = incoming.get('id')
        idx = next((i for i, sh in enumerate(sheets) if sh.get('id') == sheet_id), None) if sheet_id is not None else None

        if idx is not None:
            sheets[idx] = incoming
        else:
            if sheet_id is None:
                incoming['id'] = int(time.time() * 1000)
            sheets.append(incoming)

        song['sheet_data'] = sheets
        save_songs(songs)

        return jsonify({"message": "Partitura salva com sucesso!", "id": incoming['id']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@songs_bp.route('/add_song', methods=['POST'])
@login_required
def add_song():
    """Adiciona uma nova música."""
    import sys
    sys.stdout.flush()  # Força flush do stdout

    logger.debug("🎼 [DEBUG] Iniciando add_song...")

    title = request.form['title']
    author = request.form['author']
    sections = request.form.getlist('sections[]')
    texts = request.form.getlist('texts[]')

    logger.debug(f"📝 [DEBUG] Título: {title}")
    logger.debug(f"👤 [DEBUG] Autor: {author}")
    logger.debug(f"📄 [DEBUG] Textos: {texts}")

    # Captura dados da partitura se enviados
    sheet_data_json = request.form.get('sheet_data')
    logger.debug(f"🎵 [DEBUG] Sheet data recebido: {bool(sheet_data_json)}")
    if sheet_data_json:
        logger.debug(f"📊 [DEBUG] Tamanho dos dados: {len(sheet_data_json)} caracteres")
        logger.debug(f"📋 [DEBUG] Primeiros 200 chars: {sheet_data_json[:200]}...")

    # Captura URL do vídeo de referência
    video_url = request.form.get('video_url', '').strip()
    if video_url:
        logger.debug(f"🎬 [DEBUG] Video URL recebido: {video_url}")

    # Captura URL do áudio local
    audio_url = request.form.get('audio_url', '').strip()
    if audio_url:
        logger.debug(f"🎵 [DEBUG] Audio URL recebido: {audio_url}")

    songs = load_songs()
    new_song = {
        "id": get_next_id(songs),
        "title": title,
        "author": author,
        "sections": [
            {"title": sections[i], "text": [texts[i]]} for i in range(len(sections))
        ]
    }

    # Adiciona URL do vídeo se fornecida
    if video_url:
        new_song["video_url"] = video_url

    # Adiciona URL do áudio se fornecida
    if audio_url:
        new_song["audio_url"] = audio_url

    logger.debug(f"🆔 [DEBUG] Nova música ID: {new_song['id']}")

    # Se há dados de partitura, adiciona ao objeto da música
    if sheet_data_json:
        try:
            sheet_data = json.loads(sheet_data_json)
            new_song["sheet_data"] = sheet_data

            # Verifica se é array (múltiplas partituras) ou objeto (partitura única)
            if isinstance(sheet_data, list):
                total_notes = sum(_count_notes(s) for s in sheet_data)
                logger.debug(f"✅ [DEBUG] {len(sheet_data)} partitura(s) adicionada(s) com {total_notes} notas no total")
            else:
                logger.debug(f"✅ [DEBUG] Sheet data adicionado com {_count_notes(sheet_data)} notas")
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}")

    # Verifica se alguma seção tem marcador de partitura integrada
    for section in new_song["sections"]:
        for i, text in enumerate(section["text"]):
            if "[🎼 PARTITURA_INTEGRADA]" in text:
                logger.debug(f"🔍 [DEBUG] Marcador encontrado no texto: {text}")
                # Se há dados de partitura, substitui o marcador
                if sheet_data_json:
                    try:
                        sheet_data = json.loads(sheet_data_json)
                        new_song["sheet_data"] = sheet_data
                        logger.debug(f"✅ [DEBUG] Dados da partitura processados e salvos")
                        # Remove o marcador do texto
                        section["text"][i] = text.replace("[🎼 PARTITURA_INTEGRADA]", "").strip()
                        # Remove linhas vazias resultantes
                        section["text"] = [t for t in section["text"] if t.strip()]
                        logger.debug(f"🧹 [DEBUG] Marcador removido do texto")
                    except Exception as e:
                        logger.debug(f"❌ [DEBUG] Erro ao processar marcador: {e}")
                break

    logger.debug(f"💾 [DEBUG] Salvando música com sheet_data: {bool(new_song.get('sheet_data'))}")
    if new_song.get('sheet_data'):
        sheet_data = new_song['sheet_data']
        if isinstance(sheet_data, list):
            total_notes = sum(_count_notes(s) for s in sheet_data)
            logger.debug(f"📊 [DEBUG] {len(sheet_data)} partitura(s) na música final com {total_notes} notas no total")
        else:
            logger.debug(f"📊 [DEBUG] Notas na música final: {_count_notes(sheet_data)}")

    songs.append(new_song)
    save_songs(songs)

    logger.debug(f"✅ [DEBUG] Música salva com sucesso!")
    return jsonify({"message": "Música adicionada com sucesso!"})

@songs_bp.route('/edit_song/<int:song_id>', methods=['GET', 'POST'])
@login_required
def edit_song(song_id):
    """Edita uma música existente."""
    songs = load_songs()

    if request.method == 'POST':
        # Usa a mesma lógica do add_song
        title = request.form['title']
        author = request.form['author']
        sections = request.form.getlist('sections[]')
        texts = request.form.getlist('texts[]')
        sheet_data_json = request.form.get('sheet_data')
        video_url = request.form.get('video_url', '').strip()
        audio_url = request.form.get('audio_url', '').strip()

        logger.debug(f"🔄 [DEBUG] Editando música ID: {song_id}")
        if video_url:
            logger.debug(f"🎬 [DEBUG] Video URL: {video_url}")
        if audio_url:
            logger.debug(f"🎵 [DEBUG] Audio URL: {audio_url}")
        logger.debug(f"📝 [DEBUG] Título: {title}")
        logger.debug(f"👤 [DEBUG] Autor: {author}")
        logger.debug(f"📋 [DEBUG] Seções recebidas: {len(sections)}")
        logger.debug(f"📄 [DEBUG] Textos recebidos: {len(texts)}")
        # DEBUG: Mostra espaços no primeiro texto
        if texts:
            logger.debug(f"🔍 [DEBUG] Primeiro texto (repr): {repr(texts[0])}")
            logger.debug(f"🔍 [DEBUG] Espaços no primeiro texto: {texts[0].count(' ')}")
            logger.debug(f"🔍 [DEBUG] Primeiros 100 chars: {repr(texts[0][:100])}")
            logger.debug(f"🔍 [DEBUG] Começa com espaço? {texts[0].startswith(' ')}")

        # Encontra a música existente
        song_to_update = None
        for song in songs:
            if song['id'] == song_id:
                song_to_update = song
                break

        if not song_to_update:
            return jsonify({"error": "Música não encontrada!"}), 404

        # Atualiza os dados
        song_to_update.update({
            "title": title,
            "author": author,
            "sections": [
                {"title": sections[i], "text": [texts[i]]} for i in range(len(sections))
            ]
        })

        # Se há dados de partitura, adiciona/atualiza
        if sheet_data_json:
            try:
                sheet_data = json.loads(sheet_data_json)
                song_to_update["sheet_data"] = sheet_data

                # Verifica se é array (múltiplas partituras) ou objeto (partitura única)
                if isinstance(sheet_data, list):
                    total_notes = sum(_count_notes(s) for s in sheet_data)
                    logger.debug(f"✅ [DEBUG] {len(sheet_data)} partitura(s) atualizada(s) com {total_notes} notas no total")
                else:
                    logger.debug(f"✅ [DEBUG] Partitura atualizada com {_count_notes(sheet_data)} notas")
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"❌ [DEBUG] Erro ao fazer parse do JSON: {e}")

        # Atualiza URL do vídeo
        if video_url:
            song_to_update["video_url"] = video_url
        elif "video_url" in song_to_update and not video_url:
            # Remove se estava preenchido e agora está vazio
            del song_to_update["video_url"]

        # Atualiza URL do áudio
        if audio_url:
            song_to_update["audio_url"] = audio_url
        elif "audio_url" in song_to_update and not audio_url:
            # Remove se estava preenchido e agora está vazio
            del song_to_update["audio_url"]

        save_songs(songs)
        logger.debug(f"✅ [DEBUG] Música {song_id} editada com sucesso!")
        return jsonify({"message": "Música editada com sucesso!"})

    song_to_edit = next((song for song in songs if song['id'] == song_id), None)
    return render_template('edit_song.html', song=song_to_edit)

@songs_bp.route('/delete_song/<int:song_id>', methods=['POST'])
@login_required
def delete_song(song_id):
    """Exclui uma música."""
    songs = load_songs()
    songs = [s for s in songs if s['id'] != song_id]
    save_songs(songs)

    return jsonify({'message': 'Música removida com sucesso!'})

@songs_bp.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify([])  # Retorna lista vazia se não houver consulta

    # Carregar as músicas do arquivo sempre que a pesquisa for feita
    songs = load_songs()  # Carrega as músicas do arquivo

    results = []
    for song in songs:
        # Verificar se o título ou autor contém a consulta
        if query in song["title"].lower() or query in song["author"].lower():
            if song not in results:  # Evita duplicatas
                results.append(song)
            continue

        # Verificar se a letra contém a consulta
        for section in song["sections"]:
            for line in section["text"]:
                if query in line.lower():
                    if song not in results:  # Evita duplicatas
                        results.append(song)
                    break

    return jsonify(results)
