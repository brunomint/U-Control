"""Auditoria só-leitura das partituras (SheetData) já salvas no banco —
usado pra escolher músicas reais como fixture de teste na unificação de
renderização VexFlow (ver plano em .claude/plans/harmonic-mixing-breeze.md).

Reporta, por partitura: música/id, se está no formato canônico (measures
aninhado) ou antigo (notes achatado), time_signature, se tem acidentes/
pausas/notas pontuadas/cifras. Não modifica nada.

Uso: python scripts/audit_sheet_data.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from models_songs import SheetData, Song  # noqa: E402


def describe_sheet(sd):
    notes = sd.measures or []
    is_canonical = bool(notes) and isinstance(notes[0], list)

    if is_canonical:
        flat = [n for measure in notes for n in measure]
    else:
        flat = notes

    has_rest = any(n.get('rest') for n in flat)
    has_dotted = any(n.get('dotted') for n in flat)
    has_accidental = any(n.get('accidental') for n in flat) or any(
        c in str(n.get('pitch') or n.get('keys', [''])[0]) for n in flat for c in ('#', 'b')
    )
    has_chords = bool(sd.chords)

    return {
        'format': 'canonico (measures)' if is_canonical else 'antigo (notes achatado)',
        'time_signature': sd.time_signature,
        'clef': sd.clef,
        'key_sig': sd.key_sig,
        'n_notes': len(flat),
        'has_rest': has_rest,
        'has_dotted': has_dotted,
        'has_accidental': has_accidental,
        'has_chords': has_chords,
    }


def main():
    with app.app_context():
        sheets = SheetData.query.order_by(SheetData.song_id).all()
        if not sheets:
            print("Nenhuma partitura (SheetData) encontrada no banco.")
            return

        song_titles = {s.id: s.title for s in Song.query.all()}

        print(f"{len(sheets)} partitura(s) encontrada(s):\n")
        for sd in sheets:
            info = describe_sheet(sd)
            title = song_titles.get(sd.song_id, '???')
            print(f"song_id={sd.song_id} ({title!r}) sheet_id={sd.id} client_id={sd.client_id}")
            for k, v in info.items():
                print(f"    {k}: {v}")
            print()


if __name__ == '__main__':
    main()
