"""Importação única de orders.json, order_templates.json e
section_templates.json pras tabelas Order/OrderItem/EventoItem/
OrderTemplate/SectionTemplate (Fase 5.5).

Só leitura dos arquivos JSON originais — nunca apaga/modifica. Roda
contra o banco local de desenvolvimento (nunca o Pi). Seguro de rodar de
novo: se as tabelas já tiverem linha, aborta sem duplicar (a menos que
--force).

Normaliza um bug de dado real e pré-existente: section_templates.json's
midia.equipe está gravado como string em vez de lista (enquanto toda
ordem real tem equipe como lista) — se não normalizar aqui, o bug só
muda de lugar e ainda quebra a primeira vez que o template for aplicado
numa ordem de verdade (api_apply_section_template_month copia o campo
verbatim).

Uso: python scripts/import_orders.py [--force]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from models_orders import Order, OrderTemplate, SectionTemplate  # noqa: E402
from orders_store import save_orders, save_section_templates, save_templates_file  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_backup_pre_sql')


def _read_json(filename):
    path = os.path.join(ROOT, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _normalize_equipe(value):
    if isinstance(value, str):
        return [line.strip() for line in value.split('\n') if line.strip()]
    return value


def _normalize_section_templates(data):
    midia_tpls = data.get('midia')
    if not midia_tpls:
        return data
    for tpl in midia_tpls.values():
        if 'equipe' in tpl:
            tpl['equipe'] = _normalize_equipe(tpl['equipe'])
    return data


def main():
    force = '--force' in sys.argv

    with app.app_context():
        has_data = Order.query.first() or OrderTemplate.query.first() or SectionTemplate.query.first()
        if has_data and not force:
            print("Alguma das tabelas (order/order_template/section_template) já tem dado. "
                  "Use --force pra importar mesmo assim.")
            return

        orders = _read_json('orders.json') or {}
        save_orders(orders)
        print(f"Importadas {len(orders)} ordens de orders.json.")

        templates = _read_json('order_templates.json') or {}
        save_templates_file(templates)
        print(f"Importados {len(templates)} templates de order_templates.json.")

        section_templates = _normalize_section_templates(_read_json('section_templates.json') or {})
        save_section_templates(section_templates)
        total_sections = sum(len(v) for v in section_templates.values())
        print(f"Importados {total_sections} section-templates de section_templates.json "
              f"(equipe normalizada de string pra lista onde necessário).")


if __name__ == '__main__':
    main()
