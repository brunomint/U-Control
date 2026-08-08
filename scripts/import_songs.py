"""Importação única de songs.json pras tabelas Song/SongSection/SheetData
(Fase 5.4).

Só leitura do arquivo JSON original — nunca apaga/modifica. Roda contra o
banco local de desenvolvimento (nunca o Pi). Seguro de rodar de novo: se
a tabela Song já tiver linha, aborta sem duplicar (a menos que --force).

Preserva o `id` de cada música exatamente como está no JSON — são
referenciados em /lyrics/<id>, /edit_song/<id>, QR codes e links
externos, não podem ser reatribuídos.

Uso: python scripts/import_songs.py [--force]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from models_songs import Song  # noqa: E402
from songs_store import save_songs  # noqa: E402

JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data_backup_pre_sql', 'songs.json',
)


def main():
    force = '--force' in sys.argv

    with app.app_context():
        existing = Song.query.count()
        if existing and not force:
            print(f"Tabela song já tem {existing} linha(s). Use --force pra importar mesmo assim.")
            return

        if not os.path.exists(JSON_PATH):
            print(f"Arquivo não encontrado: {JSON_PATH}")
            return

        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            songs = json.load(f)

        save_songs(songs)
        print(f"Importadas {len(songs)} músicas de {JSON_PATH} pra tabela song.")


if __name__ == '__main__':
    main()
