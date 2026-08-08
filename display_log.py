"""Histórico do que foi exibido (bíblia, imagem, vídeo, música, ticker) —
arquivo JSON simples, sem dependência de Flask/db. Usado por várias áreas
(dashboard, bíblia, display, ticker, songs), por isso vive num módulo à
parte em vez de dentro de qualquer blueprint específico."""
import json
import os
from datetime import datetime

DISPLAY_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'display_log.json')


def load_display_log():
    try:
        with open(DISPLAY_LOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def append_display_log(entry):
    log = load_display_log()
    entry['ts'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    log.append(entry)
    if len(log) > 2000:
        log = log[-2000:]
    try:
        with open(DISPLAY_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False)
    except Exception:
        pass
