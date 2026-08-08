"""Importação única de display_log.json pra tabela DisplayLog (Fase 5.2).

Só leitura do arquivo JSON original — nunca apaga/modifica. Roda contra o
banco local de desenvolvimento (nunca o Pi). Seguro de rodar de novo: se a
tabela já tiver linhas, aborta sem duplicar (a menos que --force).

Uso: python scripts/import_display_log.py [--force]
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from extensions import db  # noqa: E402
from models import DisplayLog  # noqa: E402

JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data_backup_pre_sql', 'display_log.json',
)


def main():
    force = '--force' in sys.argv

    with app.app_context():
        existing = DisplayLog.query.count()
        if existing and not force:
            print(f"Tabela display_log já tem {existing} linha(s). Use --force pra importar mesmo assim.")
            return

        if not os.path.exists(JSON_PATH):
            print(f"Arquivo não encontrado: {JSON_PATH}")
            return

        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            entries = json.load(f)

        imported = 0
        for entry in entries:
            ts_str = entry.get('ts')
            try:
                ts = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S')
            except (TypeError, ValueError):
                ts = datetime.now()
            db.session.add(DisplayLog(
                type=entry.get('type'),
                title=entry.get('title'),
                url=entry.get('url'),
                ts=ts,
            ))
            imported += 1

        db.session.commit()
        print(f"Importadas {imported} entradas de {JSON_PATH} pra tabela display_log.")


if __name__ == '__main__':
    main()
