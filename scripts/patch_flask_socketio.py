"""Aplica o patch manual que o flask_socketio 5.6.0 precisa pra funcionar
com Flask 3.x (RequestContext.session virou privado). Idempotente — pode
rodar quantas vezes quiser, só edita se ainda não tiver sido aplicado.

Uso: python scripts/patch_flask_socketio.py
Roda tanto localmente (depois de recriar a venv) quanto no CI.
"""
import flask_socketio
import sys

OLD = "                ctx.session = session_obj\n"
NEW = "                ctx._session = session_obj\n"


def main():
    target = flask_socketio.__file__
    with open(target, encoding="utf-8") as f:
        content = f.read()

    if NEW in content:
        print(f"Já patcheado: {target}")
        return 0

    if OLD not in content:
        print(
            f"ERRO: linha esperada não encontrada em {target}. "
            "O flask_socketio pode ter mudado de versão — revise o patch manualmente.",
            file=sys.stderr,
        )
        return 1

    content = content.replace(OLD, NEW)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patch aplicado: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
