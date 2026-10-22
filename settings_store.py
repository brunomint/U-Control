"""Configurações persistidas na tabela Setting (linha única) — substitui o
antigo settings.json. Usado pela tradução preferida da Bíblia e pelo tema
(claro/escuro) do display. Mantém o mesmo formato de dict de antes
(load_settings()/save_settings(dict)) pra não exigir mudança nos
consumidores (blueprints/bible.py, blueprints/display.py)."""
from extensions import db
from models import Setting


def _get_or_create():
    row = Setting.query.first()
    if not row:
        row = Setting()
        db.session.add(row)
        db.session.commit()
    return row


def load_settings():
    """Carrega as configurações."""
    row = Setting.query.first()
    if not row:
        return {}
    settings = {}
    if row.bible_translation is not None:
        settings['bible_translation'] = row.bible_translation
    if row.bible_translation_2:
        settings['bible_translation_2'] = row.bible_translation_2
    if row.display_bg_dark is not None:
        settings['display_bg_dark'] = row.display_bg_dark
    return settings


def save_settings(settings):
    """Salva as configurações (mescla com o que já existe, igual antes —
    chamadores fazem load, mutam uma chave, e chamam save com o dict
    inteiro)."""
    row = _get_or_create()
    if 'bible_translation' in settings:
        row.bible_translation = settings['bible_translation']
    if 'bible_translation_2' in settings:
        row.bible_translation_2 = settings['bible_translation_2'] or None
    if 'display_bg_dark' in settings:
        row.display_bg_dark = settings['display_bg_dark']
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()
