"""Acesso a songs.json — usado pelo blueprint de songs (CRUD) e também
pela área de letras em main.py (lyrics, api_lyrics, section, etc.) e por
/view/<song_id>, por isso vive num módulo à parte em vez de dentro do
blueprint."""
import json
import os
import re

# Achado durante a extração, não corrigido aqui: songs_cache nunca é lido
# em lugar nenhum (só escrito), e format_lyrics() nunca é chamada — nenhum
# dos dois tem efeito hoje. Movidos como estavam.


def load_songs():
    """Carrega as músicas do arquivo JSON."""
    if not os.path.exists('songs.json'):
        return []
    with open('songs.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def save_songs(songs):
    """Salva as músicas no arquivo JSON e atualiza a cache."""
    global songs_cache
    with open('songs.json', 'w', encoding='utf-8') as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)
    songs_cache = songs  # Atualiza a cache


def get_next_id(songs):
    """Obtém o próximo ID disponível para uma nova música."""
    return max((song['id'] for song in songs), default=0) + 1


def format_lyrics(text):
    """Formata os acordes nas letras das músicas."""
    chord_pattern = r'\b[A-G][#b]?[mM]?[7-9]?\b'
    return re.sub(chord_pattern, r'<span class="chord">\g<0></span>', text)
