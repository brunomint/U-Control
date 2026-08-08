"""Histórico do que foi exibido (bíblia, imagem, vídeo, música, ticker) —
tabela SQL (DisplayLog, em models.py), substituindo o antigo
display_log.json. Usado por várias áreas (dashboard, bíblia, display,
ticker, songs), por isso vive num módulo à parte em vez de dentro de
qualquer blueprint específico.

`append_display_log` agora é um INSERT real (era leitura+append+
truncagem+reescrita do arquivo inteiro a cada chamada). `load_display_log`
mantém o mesmo formato de retorno de antes — lista de dicts, mais antigo
primeiro, `ts` como string "%Y-%m-%dT%H:%M:%S" — pra não exigir nenhuma
mudança nos consumidores (blueprints/auth.py, blueprints/utils.py)."""
from datetime import datetime

from extensions import db
from models import DisplayLog

MAX_ENTRIES = 2000


def _serialize(entry):
    return {
        'type': entry.type,
        'title': entry.title,
        'url': entry.url,
        'ts': entry.ts.strftime('%Y-%m-%dT%H:%M:%S'),
    }


def load_display_log():
    try:
        rows = DisplayLog.query.order_by(DisplayLog.id.asc()).all()
        return [_serialize(r) for r in rows]
    except Exception:
        return []


def append_display_log(entry):
    row = DisplayLog(
        type=entry.get('type'),
        title=entry.get('title'),
        url=entry.get('url'),
        ts=datetime.now(),
    )
    try:
        db.session.add(row)
        db.session.commit()

        # Mantém o mesmo cap de 2000 entradas que o arquivo JSON tinha.
        count = DisplayLog.query.count()
        if count > MAX_ENTRIES:
            excess = count - MAX_ENTRIES
            oldest_ids = [
                r.id for r in DisplayLog.query.order_by(DisplayLog.id.asc()).limit(excess).all()
            ]
            DisplayLog.query.filter(DisplayLog.id.in_(oldest_ids)).delete(synchronize_session=False)
            db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        # Vários chamadores (blueprints/display.py) fazem isso dentro de um
        # handler de socket que em seguida sobe uma thread própria pra
        # salvar DisplayState de forma assíncrona — libera a conexão de
        # volta pro pool aqui pra não sobrepor com o app_context daquela
        # thread (evita "cannot rollback - no transaction is active" sob
        # concorrência real).
        db.session.close()


def clear_display_log():
    try:
        db.session.query(DisplayLog).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()
