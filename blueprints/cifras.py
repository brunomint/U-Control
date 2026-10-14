"""Cifras (Cifra Club) e download/gestão de áudio do YouTube. Bloco
autocontido — nenhuma rota é referenciada por url_for() em lugar nenhum
do projeto (chamadas via fetch() no JS dos templates)."""
import importlib.util
import json
import logging
import os
import re
import sys

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger('ucontrol')

cifras_bp = Blueprint('cifras', __name__)


def _extrair_titulo_compositor_cifra(soup):
    """Extrai título/compositor/cifra de uma página do Cifra Club.

    Achado ao vivo (2026-08-18, "Tantos Mares" de Pedro Valença): o Cifra
    Club reescreveu o HTML pra classes com hash que mudam a cada build —
    os seletores antigos (h1.t1, h2.t3, .cifra_cnt) não existem mais na
    página, e a cifra vinha sempre vazia ("Cifra não encontrada"), sem
    nenhum log avisando. Título/compositor vêm agora do JSON-LD padrão
    schema.org (MusicComposition) que o Cifra Club já inclui pra SEO —
    isso não muda a cada redesign do jeito que classes CSS mudam. A cifra
    em si vem do <pre data-chord-content="true">, o bloco que hoje
    contém o texto com acordes (.cifra_cnt como fallback, caso o Cifra
    Club volte pro layout antigo em alguma página)."""
    titulo = compositor = None
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and data.get('@type') == 'MusicComposition':
            titulo = data.get('name')
            nomes = [c.get('name') for c in (data.get('composer') or []) if c.get('name')]
            compositor = ', '.join(nomes) if nomes else None
            break

    if not titulo:
        h1 = soup.find('h1')
        titulo = h1.get_text().strip() if h1 else None
    titulo = titulo or 'Título não encontrado'
    compositor = compositor or 'Compositor não encontrado'

    cifra_tag = soup.select_one('pre[data-chord-content="true"]') or soup.select_one('.cifra_cnt')
    if cifra_tag:
        cifra = cifra_tag.get_text().strip()
    else:
        cifra = 'Cifra não encontrada'
        logger.warning('Cifra Club: bloco de cifra não encontrado — seletor desatualizado?')

    return titulo, compositor, cifra



def _extrair_artista_cifra(soup):
    """Artista/banda como o Cifra Club escreve (com acento e maiúsculas
    certas — "MORADA", "Diante do Trono"). Vem do JSON-LD MusicRecording
    (byArtist) e, se faltar, do BreadcrumbList (3º item). Antes o editor
    montava o artista a partir do endereço ("ministerio-morada" →
    "Ministerio Morada"), sem acento."""
    trilha = None
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except (ValueError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict):
                continue
            tipos = item.get('@type')
            tipos = tipos if isinstance(tipos, list) else [tipos]
            if 'MusicRecording' in tipos:
                artista = (item.get('byArtist') or {}).get('name')
                if artista:
                    return artista.strip()
            if 'BreadcrumbList' in tipos:
                for elemento in item.get('itemListElement') or []:
                    if elemento.get('position') == 3 and elemento.get('name'):
                        trilha = elemento['name'].strip()
    return trilha


#Extrair Cifras do Cifra-CLub
@cifras_bp.route("/cifra")
def pegar_cifra():
    url = request.args.get("url")
    if not url:
        return "URL não fornecida", 400

    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')

        titulo, compositor, cifra = _extrair_titulo_compositor_cifra(soup)

        # Monta texto puro com título e compositor na frente, separados por linhas em branco
        texto_puro = f"{titulo}\n\n{compositor}\n\n{cifra}"

        return texto_puro

    except Exception as e:
        return str(e), 500

# Extrair Cifra com Vídeo do Cifra Club (retorna JSON)
@cifras_bp.route("/cifra_com_video")
def pegar_cifra_com_video():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')

        titulo, compositor, cifra = _extrair_titulo_compositor_cifra(soup)

        # Extrair URL do vídeo do YouTube
        video_url = None

        # Método 1: Procura iframe do YouTube
        iframe = soup.find('iframe', src=re.compile(r'youtube\.com|youtu\.be'))
        if iframe and iframe.get('src'):
            src = iframe.get('src')
            # Extrai o ID do vídeo
            match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})', src)
            if match:
                video_url = f"https://www.youtube.com/watch?v={match.group(1)}"

        # Método 2: Procura data-video ou atributos com ID do YouTube
        if not video_url:
            video_element = soup.find(attrs={'data-video': True})
            if video_element:
                video_id = video_element.get('data-video')
                if video_id and len(video_id) == 11:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Método 3: Procura no script da página por IDs de vídeo
        if not video_url:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Procura padrões de ID do YouTube no JavaScript
                    match = re.search(r'["\']videoId["\']\s*:\s*["\']([a-zA-Z0-9_-]{11})["\']', script.string)
                    if match:
                        video_url = f"https://www.youtube.com/watch?v={match.group(1)}"
                        break
                    # Procura URLs do YouTube diretamente
                    match = re.search(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', script.string)
                    if match:
                        video_url = f"https://www.youtube.com/watch?v={match.group(1)}"
                        break

        # Monta texto puro
        texto_puro = f"{titulo}\n\n{compositor}\n\n{cifra}"

        return jsonify({
            "titulo": titulo,
            "artista": _extrair_artista_cifra(soup),
            "compositor": compositor,
            "cifra": texto_puro,
            "video_url": video_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _yt_dlp_python():
    """Python que roda o yt-dlp: o do próprio U-Control (venv, versão do
    requirements.txt) quando ele tem o yt-dlp — antes era sempre o
    python3 do sistema, com um yt-dlp velho que o YouTube já recusava."""
    return sys.executable if importlib.util.find_spec('yt_dlp') else 'python3'


# Download de áudio do YouTube via yt-dlp
@cifras_bp.route("/download_audio", methods=["POST"])
@login_required
def download_audio():
    import subprocess

    data = request.get_json()
    video_url = data.get("url")
    song_id = data.get("song_id")  # ID da música para nomear o arquivo
    old_audio_url = data.get("old_audio_url")  # URL do áudio antigo para deletar

    if not video_url:
        return jsonify({"error": "URL não fornecida"}), 400

    try:
        # Extrai ID do vídeo para nome do arquivo
        match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', video_url)
        if not match:
            return jsonify({"error": "URL do YouTube inválida"}), 400

        video_id = match.group(1)
        # yt-dlp recebe só a URL remontada a partir do ID: o texto recebido
        # podia começar com "--exec=..." e virar opção (comando no servidor)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        # song_id entra no nome do arquivo: só número
        song_id = str(song_id) if song_id is not None and str(song_id).isdigit() else None

        # Define nome do arquivo (usa song_id se fornecido, senão video_id)
        filename = f"{song_id}_{video_id}" if song_id else video_id
        audio_dir = os.path.join(current_app.static_folder, 'audio')
        output_path = os.path.join(audio_dir, f"{filename}.mp3")

        # Deleta áudio antigo se fornecido e diferente do novo — só um .mp3
        # de dentro da pasta de áudio (antes "../../instance/users.db"
        # apagava o banco)
        if old_audio_url and old_audio_url.strip():
            old_filename = os.path.basename(old_audio_url.split('?')[0])
            old_path = os.path.join(audio_dir, old_filename)
            dentro = os.path.realpath(old_path).startswith(os.path.realpath(audio_dir) + os.sep)
            if dentro and old_filename.endswith('.mp3') and os.path.exists(old_path) and old_path != output_path:
                os.remove(old_path)
                logger.info(f"🗑️ Áudio antigo deletado: {old_path}")

        # Verifica se já existe
        if os.path.exists(output_path):
            return jsonify({
                "success": True,
                "audio_url": f"/static/audio/{filename}.mp3",
                "message": "Áudio já existe"
            })

        # Garante que a pasta existe
        os.makedirs(audio_dir, exist_ok=True)

        # Comando yt-dlp para baixar apenas áudio em MP3
        cmd = [
            _yt_dlp_python(), "-m", "yt_dlp",
            "-x",  # Extrai áudio
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", output_path.replace('.mp3', '.%(ext)s'),
            "--no-playlist",
            "--quiet",
            "--",
            video_url
        ]

        logger.info(f"🎵 Baixando áudio: {video_url}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"❌ Erro yt-dlp: {result.stderr}")
            return jsonify({"error": f"Erro ao baixar: {result.stderr}"}), 500

        # Verifica se o arquivo foi criado
        if os.path.exists(output_path):
            logger.info(f"✅ Áudio salvo: {output_path}")
            return jsonify({
                "success": True,
                "audio_url": f"/static/audio/{filename}.mp3"
            })
        else:
            return jsonify({"error": "Arquivo não foi criado"}), 500

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout ao baixar áudio"}), 500
    except Exception as e:
        logger.exception(f"❌ Erro: {str(e)}")
        return jsonify({"error": str(e)}), 500


# Listar áudios disponíveis
@cifras_bp.route("/list_audio")
def list_audio():
    audio_dir = os.path.join(current_app.static_folder, 'audio')
    if not os.path.exists(audio_dir):
        return jsonify({"audios": []})

    audios = []
    for f in os.listdir(audio_dir):
        if f.endswith('.mp3'):
            audios.append({
                "filename": f,
                "url": f"/static/audio/{f}"
            })

    return jsonify({"audios": audios})


# Deletar áudio
@cifras_bp.route("/delete_audio/<filename>", methods=["DELETE"])
@login_required
def delete_audio(filename):
    audio_path = os.path.join(current_app.static_folder, 'audio', filename)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        return jsonify({"success": True})
    return jsonify({"error": "Arquivo não encontrado"}), 404
