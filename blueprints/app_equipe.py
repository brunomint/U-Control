"""Rotas do app Android da equipe (android-equipe/, plano em docs/APP_EQUIPE.md).

/api/identidade é como o app reconhece um U-Control na rede: ele testa os
endereços do Wi-Fi na porta do U-Control e só aceita quem responde aqui
com app == "U-Control". Público como o /view e a /agenda (o app chega
antes de qualquer login) — por isso só diz o nome da igreja e a versão.

`api` sobe quando o app precisar de algo que um servidor antigo não tem.
`id` é fixo por instalação: o mesmo servidor no cabo e no Wi-Fi responde
em dois endereços, e o app mostra a igreja uma vez só."""
import os
import uuid

from flask import Blueprint, current_app, jsonify

import updates
from blueprints.agenda import nome_igreja

app_equipe_bp = Blueprint('app_equipe', __name__)

API_DO_APP = 1
_ARQUIVO_ID = 'servidor_id'
_id = None


def servidor_id():
    """Criado na primeira vez e guardado em instance/ (vai junto no backup)."""
    global _id
    if _id:
        return _id
    caminho = os.path.join(current_app.instance_path, _ARQUIVO_ID)
    try:
        with open(caminho, encoding='utf-8') as f:
            _id = f.read().strip() or None
    except OSError:
        pass
    if not _id:
        _id = uuid.uuid4().hex
        try:
            os.makedirs(current_app.instance_path, exist_ok=True)
            with open(caminho, 'w', encoding='utf-8') as f:
                f.write(_id)
        except OSError:
            pass   # sem gravar, vale até reiniciar — o app só repetiria a igreja
    return _id


@app_equipe_bp.route('/api/identidade')
def api_identidade():
    resposta = jsonify({
        'app': 'U-Control',
        'versao': updates.current_version(),
        'api': API_DO_APP,
        'id': servidor_id(),
        'igreja': nome_igreja(),
    })
    # A varredura testa dezenas de endereços: nada de guardar resposta velha
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta
