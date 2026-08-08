"""Importação única de settings.json, image_paths.json e urls.json pras
tabelas Setting/ImagePath/SavedUrls (Fase 5.3a).

Só leitura dos arquivos JSON originais — nunca apaga/modifica. Roda
contra o banco local de desenvolvimento (nunca o Pi). Seguro de rodar de
novo: se as tabelas já tiverem linha, aborta sem duplicar (a menos que
--force).

Uso: python scripts/import_configs.py [--force]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from extensions import db  # noqa: E402
from models import ImagePath, SavedUrls, Setting  # noqa: E402

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
        if Setting.query.first() or ImagePath.query.first() or SavedUrls.query.first():
            if not force:
                print("Alguma das tabelas (setting/image_path/saved_urls) já tem dado. "
                      "Use --force pra importar mesmo assim.")
                return

        settings = _read_json('settings.json') or {}
        db.session.add(Setting(
            bible_translation=settings.get('bible_translation'),
            display_bg_dark=settings.get('display_bg_dark'),
        ))

        image_paths = _read_json('image_paths.json') or {}
        db.session.add(ImagePath(image=image_paths.get('image')))

        urls = _read_json('urls.json') or {}
        db.session.add(SavedUrls(
            url1=urls.get('url1'),
            url2=urls.get('url2'),
            url3=urls.get('url3'),
        ))

        db.session.commit()
        print("Importados settings.json, image_paths.json e urls.json.")


if __name__ == '__main__':
    main()
