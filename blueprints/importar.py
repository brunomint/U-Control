"""Importar músicas de outros programas (Holyrics, OpenLP/OpenLyrics,
ChordPro, texto). A leitura dos arquivos é importar_musicas.py; aqui fica
o passo a passo:

1. /api/importar-musicas/analisar recebe os arquivos, lê e compara com as
   músicas daqui (mesmo título e artista = mesma música): nova, igual ou
   diferente. As lidas ficam num arquivo temporário (token), pra não ir e
   voltar do navegador — um hinário tem mais de mil.
2. /api/importar-musicas/importar grava as escolhidas: novas entram com id
   novo; nas que já existem e estão diferentes, a pessoa escolhe substituir
   ou pular (padrão: pular, pra não estragar uma cifra ajustada aqui)."""
import json
import os
import re
import time
import uuid

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required

import importar_musicas
from i18n import gettext as _
from songs_store import chave_musica, get_song, musicas_por_chave, next_song_id, save_song

importar_bp = Blueprint('importar', __name__)

_VALIDADE = 3600
LIMITE_ENVIO = 80 * 1024 * 1024


def _pasta_temp():
    pasta = os.path.join(current_app.instance_path, 'importacoes')
    os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        caminho = os.path.join(pasta, f)
        if time.time() - os.path.getmtime(caminho) > _VALIDADE:
            os.remove(caminho)
    return pasta


def _conteudo(m):
    return json.dumps(m['sections'], sort_keys=True, ensure_ascii=False)


def _preview(m):
    texto = m['sections'][0]['text'][0] if m['sections'] else ''
    return '\n'.join(texto.split('\n')[:4])


@importar_bp.route('/importar-musicas')
@login_required
def importar_page():
    return render_template('importar_musicas.html')


@importar_bp.route('/api/importar-musicas/analisar', methods=['POST'])
@login_required
def api_analisar():
    arquivos = [f for f in request.files.getlist('arquivos') if f and f.filename]
    if not arquivos:
        return jsonify({'error': _('Escolha os arquivos das músicas.')}), 400
    musicas, erros, total = [], [], 0
    for arq in arquivos:
        dados = arq.read(LIMITE_ENVIO + 1)
        total += len(dados)
        if total > LIMITE_ENVIO:
            return jsonify({'error': _('Arquivos grandes demais (máximo 80 MB por vez).')}), 400
        try:
            musicas += importar_musicas.ler(arq.filename, dados)
        except importar_musicas.ArquivoInvalido as e:
            erros.append(str(e))
    if not musicas:
        return jsonify({'error': ' '.join(erros) or _('Nenhuma música reconhecida.'), 'erros': erros}), 400

    daqui = musicas_por_chave()
    vistas = set()
    lista = []
    for i, m in enumerate(musicas):
        chave = chave_musica(m['title'], m['author'])
        if chave in vistas:
            status = 'repetida'  # a mesma música duas vezes nos arquivos
        elif chave in daqui:
            atual = get_song(daqui[chave]) or {}
            status = 'igual' if json.dumps([{'title': s.get('title') or '', 'text': s.get('text')} for s in atual.get('sections', [])],
                                           sort_keys=True, ensure_ascii=False) == _conteudo(m) else 'diferente'
        else:
            status = 'nova'
        vistas.add(chave)
        lista.append({'i': i, 'title': m['title'], 'author': m['author'], 'secoes': len(m['sections']),
                      'origem': m['origem'], 'status': status, 'preview': _preview(m)})

    token = uuid.uuid4().hex
    with open(os.path.join(_pasta_temp(), token + '.json'), 'w', encoding='utf-8') as f:
        json.dump(musicas, f, ensure_ascii=False)
    return jsonify({'token': token, 'musicas': lista, 'erros': erros})


@importar_bp.route('/api/importar-musicas/importar', methods=['POST'])
@login_required
def api_importar():
    pedido = request.get_json(silent=True) or {}
    token = pedido.get('token') or ''
    if not re.fullmatch(r'[0-9a-f]{32}', token):
        return jsonify({'error': _('Importação não encontrada. Envie os arquivos de novo.')}), 400
    caminho = os.path.join(_pasta_temp(), token + '.json')
    if not os.path.exists(caminho):
        return jsonify({'error': _('Importação não encontrada. Envie os arquivos de novo.')}), 400
    with open(caminho, encoding='utf-8') as f:
        musicas = json.load(f)
    escolhidas = {int(i) for i in pedido.get('importar', []) if str(i).isdigit()}
    substituir = {int(i) for i in pedido.get('substituir', []) if str(i).isdigit()}

    daqui = musicas_por_chave()
    feito = {'novas': 0, 'substituidas': 0, 'puladas': 0}
    for i, m in enumerate(musicas):
        if i not in escolhidas:
            continue
        chave = chave_musica(m['title'], m['author'])
        # order: Ordem no culto do arquivo (OpenSong, OpenLyrics); sem ela,
        # None — numa música substituída, a ordem antiga não vale pras seções novas
        dados = {'title': m['title'], 'author': m['author'], 'sections': m['sections'], 'order': m.get('order')}
        if chave in daqui:
            if i not in substituir:
                feito['puladas'] += 1
                continue
            antiga = get_song(daqui[chave]) or {}
            # mantém o que só existe aqui (partitura, vídeo, áudio, tema)
            save_song({**{k: v for k, v in antiga.items() if k != 'last_played'}, **dados, 'id': daqui[chave]})
            feito['substituidas'] += 1
        else:
            novo = next_song_id()
            save_song({**dados, 'id': novo})
            daqui[chave] = novo
            feito['novas'] += 1
    os.remove(caminho)
    current_app.logger.info('importar músicas: %s', feito)
    return jsonify({'ok': True, **feito})
