"""Importação única de countdown_config.json e ticker_config.json pras
tabelas CountdownConfig/TickerConfig (Fase 5.3b).

Só leitura dos arquivos JSON originais — nunca apaga/modifica. Roda
contra o banco local de desenvolvimento (nunca o Pi). Seguro de rodar de
novo: se as tabelas já tiverem linha, aborta sem duplicar (a menos que
--force).

Uso: python scripts/import_countdown_ticker.py [--force]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from extensions import db  # noqa: E402
from models import CountdownConfig, TickerConfig  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_json(filename):
    path = os.path.join(ROOT, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    force = '--force' in sys.argv

    with app.app_context():
        if CountdownConfig.query.first() or TickerConfig.query.first():
            if not force:
                print("countdown_config/ticker_config já têm dado. Use --force pra importar mesmo assim.")
                return

        countdown = _read_json('countdown_config.json') or {}
        db.session.add(CountdownConfig(label=countdown.get('label')))

        ticker = _read_json('ticker_config.json') or {}
        db.session.add(TickerConfig(text=ticker.get('text')))

        db.session.commit()
        print("Importados countdown_config.json e ticker_config.json.")


if __name__ == '__main__':
    main()
