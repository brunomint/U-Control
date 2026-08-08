"""Cifras (Cifra Club) e download/gestão de áudio do YouTube. Bloco
autocontido — nenhuma rota é referenciada por url_for() em lugar nenhum
do projeto (chamadas via fetch() no JS dos templates)."""
import logging
import os
import re

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger('ucontrol')

cifras_bp = Blueprint('cifras', __name__)


#Extrair Cifras do Cifra-CLub
@cifras_bp.route("/cifra")
def pegar_cifra():
    url = request.args.get("url")
    if not url:
        return "URL não fornecida", 400

    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(r.text, 'html.parser')

        # Título
        titulo_tag = soup.find('h1', class_='t1')
        titulo = titulo_tag.text.strip() if titulo_tag else 'Título não encontrado'

        # Compositor
        compositor_tag = soup.find('h2', class_='t3')
        compositor = compositor_tag.text.strip() if compositor_tag else 'Compositor não encontrado'

        # Cifra
        cifra_tag = soup.select_one('.cifra_cnt')
        cifra = cifra_tag.get_text().strip() if cifra_tag else 'Cifra não encontrada'

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

        # Título
        titulo_tag = soup.find('h1', class_='t1')
        titulo = titulo_tag.text.strip() if titulo_tag else 'Título não encontrado'

        # Compositor
        compositor_tag = soup.find('h2', class_='t3')
        compositor = compositor_tag.text.strip() if compositor_tag else 'Compositor não encontrado'

        # Cifra
        cifra_tag = soup.select_one('.cifra_cnt')
        cifra = cifra_tag.get_text().strip() if cifra_tag else 'Cifra não encontrada'

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
            "compositor": compositor,
            "cifra": texto_puro,
            "video_url": video_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Download de áudio do YouTube via yt-dlp
@cifras_bp.route("/download_audio", methods=["POST"])
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

        # Define nome do arquivo (usa song_id se fornecido, senão video_id)
        filename = f"{song_id}_{video_id}" if song_id else video_id
        audio_dir = os.path.join(current_app.static_folder, 'audio')
        output_path = os.path.join(audio_dir, f"{filename}.mp3")

        # Deleta áudio antigo se fornecido e diferente do novo
        if old_audio_url and old_audio_url.strip():
            old_filename = old_audio_url.replace('/static/audio/', '')
            old_path = os.path.join(audio_dir, old_filename)
            if os.path.exists(old_path) and old_path != output_path:
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
            "python3", "-m", "yt_dlp",
            "-x",  # Extrai áudio
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", output_path.replace('.mp3', '.%(ext)s'),
            "--no-playlist",
            "--quiet",
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
