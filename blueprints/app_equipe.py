"""Rotas do app Android da equipe (android-equipe/, plano em docs/APP_EQUIPE.md).

/api/identidade é como o app reconhece um U-Control na rede: ele testa os
endereços do Wi-Fi na porta do U-Control e só aceita quem responde aqui
com app == "U-Control". Público como o /view e a /agenda (o app chega
antes de qualquer login) — por isso só diz o nome da igreja e a versão.

`api` sobe quando o app precisar de algo que um servidor antigo não tem.
`id` é fixo por instalação: o mesmo servidor no cabo e no Wi-Fi responde
em dois endereços, e o app mostra a igreja uma vez só.

/api/app/salvar e /api/app/musicas dizem ao app o que guardar no celular
(cultos dos próximos dias e as músicas das playlists) e uma `versao` de
cada coisa: o app só baixa de novo o que mudou. É o mesmo conteúdo que o
/view já mostra aberto."""
import hashlib
import json
import os
import re
import uuid
from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

import updates
from blueprints.agenda import nome_igreja

app_equipe_bp = Blueprint('app_equipe', __name__)

API_DO_APP = 2   # 2: /api/app/salvar e /api/app/musicas
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


# ------------------------------------------------- guardar no celular ---

_MUSICA_DA_ORDEM = re.compile(r'^/lyrics/(\d+)')
DIAS_PADRAO = 15


def _versao(dados):
    texto = json.dumps(dados, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(texto.encode('utf-8')).hexdigest()[:16]


def _resumo_musica(song):
    # last_played muda a cada vez que a música toca no telão: não é mudança na cifra
    conteudo = {k: v for k, v in song.items() if k != 'last_played'}
    return {'id': song['id'], 'titulo': song['title'], 'autor': song['author'],
            'versao': _versao(conteudo)}


def _ids_da_ordem(itens):
    ids = []
    for item in itens or []:
        m = _MUSICA_DA_ORDEM.match(item.get('url') or '')
        if m and int(m.group(1)) not in ids:
            ids.append(int(m.group(1)))
    return ids


def _titulo_do_culto(ordem):
    partes = [ordem.get('tipo') or 'Culto']
    if ordem.get('horario_culto'):
        partes.append(ordem['horario_culto'])
    return ' · '.join(p.strip() for p in partes if p and p.strip())


@app_equipe_bp.route('/api/app/salvar')
def api_app_salvar():
    """Cultos de hoje até `dias` à frente que têm música, com as músicas."""
    from models_orders import Order
    from orders_store import get_order
    from songs_store import get_song

    try:
        dias = max(1, min(int(request.args.get('dias', DIAS_PADRAO)), 60))
    except ValueError:
        dias = DIAS_PADRAO
    hoje = date.today()
    ate = (hoje + timedelta(days=dias + 1)).isoformat()   # '2026-12-05-2' < '2026-12-06'
    chaves = [o.date for o in Order.query.filter(Order.date >= hoje.isoformat(), Order.date < ate)
              .order_by(Order.date.asc())]

    musicas = {}
    cultos = []
    for chave in chaves:
        ordem = get_order(chave)
        ids = _ids_da_ordem(ordem.get('itens'))
        if not ids:
            continue
        for i in ids:
            if i not in musicas:
                song = get_song(i)
                musicas[i] = _resumo_musica(song) if song else None
        cultos.append({
            'chave': chave,
            'data': chave[:10],
            'titulo': _titulo_do_culto(ordem),
            'dirigente': ordem.get('dirigente') or '',
            'versao': _versao(ordem),
            'musicas': [musicas[i] for i in ids if musicas[i]],
        })

    resposta = jsonify({'versao_servidor': updates.current_version(), 'dias': dias, 'cultos': cultos})
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta


@app_equipe_bp.route('/api/app/musicas')
def api_app_musicas():
    """?ids=1,2,3 → a versão de cada música (as que não existem mais ficam de fora)."""
    from songs_store import get_song

    ids = []
    for parte in (request.args.get('ids') or '').split(','):
        if parte.strip().isdigit() and int(parte) not in ids:
            ids.append(int(parte))
    musicas = []
    for i in ids[:300]:
        song = get_song(i)
        if song:
            musicas.append(_resumo_musica(song))
    resposta = jsonify({'versao_servidor': updates.current_version(), 'musicas': musicas})
    resposta.headers['Cache-Control'] = 'no-store'
    return resposta
