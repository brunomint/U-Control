"""Configurações persistidas em settings.json — usado pela tradução
preferida da Bíblia e pelo tema (claro/escuro) do display. Puro stdlib,
sem dependência de Flask/db, por isso vive num módulo à parte em vez de
dentro de qualquer blueprint específico."""
import json
import os

SETTINGS_FILE = os.path.join(os.getcwd(), 'settings.json')


def load_settings():
    """Carrega as configurações do arquivo JSON."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_settings(settings):
    """Salva as configurações no arquivo JSON."""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)
