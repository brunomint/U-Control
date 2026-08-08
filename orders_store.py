"""Acesso a orders.json (ordem do culto), order_templates.json e
section_templates.json. Usado pelos blueprints de ordem/agenda e também
por view_order_by_date/view_song/lyrics em main.py (núcleo de display,
área de letras — não fazem parte desta extração)."""
import json
import logging
import os

logger = logging.getLogger('ucontrol')

# Sistema legado (pré-orders.json) — só usado por /save e /load em
# blueprints/orders.py e por um fallback em view_song (main.py).
DATA_FILE = 'order_of_service.json'

ORDERS_FILE = 'orders.json'
TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'order_templates.json')
SECTION_TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'section_templates.json')


def load_templates():
    try:
        if os.path.exists(TEMPLATES_FILE):
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}


def save_templates_file(templates):
    try:
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


# Funções auxiliares para o novo sistema de ordens
def load_orders():
    """Carrega todas as ordens do arquivo orders.json"""
    try:
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.exception(f"Erro ao carregar orders.json: {e}")
        return {}


def save_orders(orders):
    """Salva todas as ordens no arquivo orders.json"""
    try:
        with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.exception(f"Erro ao salvar orders.json: {e}")
        return False


def load_section_templates():
    try:
        if os.path.exists(SECTION_TEMPLATES_FILE):
            with open(SECTION_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}


def save_section_templates(data):
    try:
        with open(SECTION_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
