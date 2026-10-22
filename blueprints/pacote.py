"""Levar músicas, cultos e fotos de um U-Control pra outro, somando ao que
já existe (o backup, em blueprints/backup.py, troca tudo). Caso típico:
preparar o culto em casa e levar pro PC da igreja.

Pacote = .zip com:
    manifest.json   {'app': 'U-Control', 'tipo': 'pacote', ...}
    pacote.json     {'musicas': [...], 'cultos': {chave: ordem}, 'pastas': [...]}
    imagens/<pasta>/<arquivo>   fotos, slides (e a versão animada) e vídeos

Importar é em dois passos: /api/pacote/analisar compara com o que existe
(música nova, igual ou diferente — mesmo título e artista; culto novo,
igual ou diferente — mesma data) e a pessoa escolhe, nas diferentes,
"a do pacote" ou "a deste computador"; /api/pacote/importar aplica.

O id da música muda de um computador pro outro: os itens do culto que
apontam pra /lyrics/<id> são reescritos pro id daqui."""
import datetime
import json
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile

from flask import Blueprint, after_this_request, current_app, jsonify, render_template, request, send_file
from flask_login import login_required

import paths
import updates
from blueprints.gallery import _safe_folder_path
from extensions import db
from orders_store import get_order, save_order
from songs_store import chave_musica, get_song, musicas_por_chave, next_song_id, save_song

pacote_bp = Blueprint('pacote', __name__)

FORMATO = 1
_RE_LYRICS = re.compile(r'^/lyrics/(\d+)(?=$|[?#/])')
_VALIDADE = 3600  # pacote enviado e não importado: apagado depois de 1 h


_chave = chave_musica  # (também usada pelo importar.py, via songs_store)


def _conteudo(song):
    """O que conta pra 'igual': tudo menos id e última vez tocada."""
    return json.dumps({k: v for k, v in song.items() if k not in ('id', 'last_played')},
                      sort_keys=True, ensure_ascii=False)


_musicas_daqui = musicas_por_chave


def _pasta_dir(nome):
    return paths.IMAGE_FOLDER if nome == 'Geral' else _safe_folder_path(nome)


def _arquivos_da_pasta(nome):
    pasta = _pasta_dir(nome)
    if not pasta or not os.path.isdir(pasta):
        return []
    return sorted(f for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f)))


def _pasta_temp():
    pasta = os.path.join(current_app.instance_path, 'pacotes')
    os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):  # sobras de importações abandonadas
        caminho = os.path.join(pasta, f)
        if time.time() - os.path.getmtime(caminho) > _VALIDADE:
            os.remove(caminho)
    return pasta


# --- Exportar -------------------------------------------------------------

def criar_pacote(destino, musicas=(), cultos=(), pastas=()):
    ids = {int(i) for i in musicas}
    dados_cultos = {}
    for chave in cultos:
        ordem = get_order(chave)
        if not ordem:
            continue
        dados_cultos[chave] = ordem
        for item in ordem.get('itens', []):  # o culto leva as músicas dele
            m = _RE_LYRICS.match(item.get('url') or '')
            if m:
                ids.add(int(m.group(1)))
    dados_musicas = [s for s in (get_song(i) for i in sorted(ids)) if s]
    for s in dados_musicas:
        s.pop('last_played', None)

    pastas = [p for p in pastas if _pasta_dir(p)]
    manifest = {'app': 'U-Control', 'tipo': 'pacote', 'formato': FORMATO,
                'versao': updates.current_version(),
                'criado': datetime.datetime.now().isoformat(timespec='seconds')}
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr('pacote.json', json.dumps(
            {'musicas': dados_musicas, 'cultos': dados_cultos, 'pastas': pastas}, ensure_ascii=False))
        for nome in pastas:
            for arq in _arquivos_da_pasta(nome):
                zf.write(os.path.join(_pasta_dir(nome), arq), f'imagens/{nome}/{arq}',
                         compress_type=zipfile.ZIP_STORED)
    return {'musicas': len(dados_musicas), 'cultos': len(dados_cultos), 'pastas': len(pastas)}


# --- Importar -------------------------------------------------------------

def _reescrever_ordem(ordem, ids):
    """Itens /lyrics/<id do pacote> -> /lyrics/<id daqui> (ids: ref -> id)."""
    def url(u):
        m = _RE_LYRICS.match(u or '')
        if m and ids.get(int(m.group(1))) is not None:
            return f'/lyrics/{ids[int(m.group(1))]}' + u[m.end():]
        return u
    ordem = dict(ordem)
    ordem['itens'] = [dict(i, url=url(i['url'])) if i.get('url') else i for i in ordem.get('itens', [])]
    return ordem


def _sem_feitos(ordem):
    return json.dumps(ordem, sort_keys=True, ensure_ascii=False)


class PacoteInvalido(Exception):
    pass


def ler_pacote(caminho):
    if not zipfile.is_zipfile(caminho):
        raise PacoteInvalido('Este arquivo não é um pacote do U-Control.')
    with zipfile.ZipFile(caminho) as zf:
        try:
            manifest = json.loads(zf.read('manifest.json'))
        except (KeyError, ValueError):
            raise PacoteInvalido('Este arquivo não é um pacote do U-Control.')
        if manifest.get('app') != 'U-Control':
            raise PacoteInvalido('Este arquivo não é um pacote do U-Control.')
        if manifest.get('tipo') != 'pacote':
            raise PacoteInvalido('Este arquivo é um backup completo: restaure em Sistema → Backup.')
        if manifest.get('formato', 0) > FORMATO:
            raise PacoteInvalido('Pacote de uma versão mais nova do U-Control. Atualize este antes de importar.')
        dados = json.loads(zf.read('pacote.json'))
        arquivos = {}
        for nome in zf.namelist():
            if nome in ('manifest.json', 'pacote.json') or nome.endswith('/'):
                continue
            partes = nome.split('/')
            if len(partes) != 3 or partes[0] != 'imagens' or partes[1] not in dados.get('pastas', []) \
                    or partes[2] in ('', '.', '..') or '\\' in nome or partes[1] in ('.', '..', ''):
                raise PacoteInvalido(f'Arquivo estranho dentro do pacote: {nome}')
            arquivos.setdefault(partes[1], []).append((partes[2], zf.getinfo(nome).file_size))
    return manifest, dados, arquivos


def analisar(caminho):
    manifest, dados, arquivos = ler_pacote(caminho)
    daqui = _musicas_daqui()
    musicas = []
    for s in dados.get('musicas', []):
        existente = daqui.get(_chave(s.get('title'), s.get('author')))
        status = 'nova'
        if existente is not None:
            status = 'igual' if _conteudo(get_song(existente) or {}) == _conteudo(s) else 'diferente'
        musicas.append({'ref': s['id'], 'title': s.get('title'), 'author': s.get('author'), 'status': status})
    # Pra comparar culto, os links /lyrics/<id do pacote> viram os ids daqui
    ids = {m['ref']: daqui.get(_chave(m['title'], m['author'])) for m in musicas}
    cultos = []
    for chave, ordem in dados.get('cultos', {}).items():
        atual = get_order(chave)
        status = 'novo'
        if atual:
            status = 'igual' if _sem_feitos(atual) == _sem_feitos(_reescrever_ordem(ordem, ids)) else 'diferente'
        cultos.append({'chave': chave, 'tipo': ordem.get('tipo'), 'tema': ordem.get('tema'), 'status': status})
    pastas = []
    for nome in dados.get('pastas', []):
        aqui = set(_arquivos_da_pasta(nome)) if _pasta_dir(nome) else set()
        lista = arquivos.get(nome, [])
        pastas.append({'nome': nome, 'arquivos': len(lista), 'ja_existem': sum(1 for a, _ in lista if a in aqui)})
    return {'manifest': manifest, 'musicas': musicas, 'cultos': cultos, 'pastas': pastas}


def importar(caminho, escolhas):
    """escolhas: {'musicas': {ref: 'pacote'|'daqui'}, 'cultos': {chave: ...}}.
    Sem escolha, fica a do pacote (é o que a pessoa trouxe pra usar)."""
    _, dados, _ = ler_pacote(caminho)
    esc_m = {str(k): v for k, v in (escolhas.get('musicas') or {}).items()}
    esc_c = escolhas.get('cultos') or {}
    daqui = _musicas_daqui()
    novo_id = {}
    feito = {'musicas_novas': 0, 'musicas_atualizadas': 0, 'cultos': 0, 'arquivos': 0}

    for s in dados.get('musicas', []):
        ref = s['id']
        existente = daqui.get(_chave(s.get('title'), s.get('author')))
        if existente is None:
            novo = next_song_id()
            save_song({**s, 'id': novo})
            daqui[_chave(s.get('title'), s.get('author'))] = novo
            novo_id[ref] = novo
            feito['musicas_novas'] += 1
            continue
        novo_id[ref] = existente
        if esc_m.get(str(ref), 'pacote') == 'pacote' and _conteudo(get_song(existente) or {}) != _conteudo(s):
            save_song({**s, 'id': existente})
            feito['musicas_atualizadas'] += 1

    for chave, ordem in dados.get('cultos', {}).items():
        if not re.match(r'^\d{4}-\d{2}-\d{2}(-\d+)?$', chave):
            continue
        if get_order(chave) and esc_c.get(chave, 'pacote') != 'pacote':
            continue
        save_order(chave, _reescrever_ordem(ordem, novo_id))
        feito['cultos'] += 1

    with zipfile.ZipFile(caminho) as zf:
        for nome in dados.get('pastas', []):
            if nome != 'Geral' and (not _pasta_dir(nome) or '/' in nome or '\\' in nome or nome.startswith('.')):
                continue
            pasta = _pasta_dir(nome)
            os.makedirs(pasta, exist_ok=True)
            for info in zf.infolist():
                if not info.filename.startswith(f'imagens/{nome}/') or info.filename.endswith('/'):
                    continue
                alvo = os.path.join(pasta, info.filename.rsplit('/', 1)[1])
                parcial = alvo + '.importando'
                with zf.open(info) as src, open(parcial, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                os.replace(parcial, alvo)
                feito['arquivos'] += 1
    return feito


# --- Rotas ----------------------------------------------------------------

@pacote_bp.route('/pacote')
@login_required
def pacote_page():
    return render_template('pacote.html')


@pacote_bp.route('/api/pacote/itens')
@login_required
def api_pacote_itens():
    from models_songs import Song
    from models_orders import Order, OrderItem
    musicas = [{'id': i, 'title': t, 'author': a}
               for i, t, a in db.session.query(Song.id, Song.title, Song.author).order_by(Song.title)]
    n_musicas = {}
    for data, url in db.session.query(OrderItem.order_date, OrderItem.url):
        if _RE_LYRICS.match(url or ''):
            n_musicas[data] = n_musicas.get(data, 0) + 1
    hoje = datetime.date.today().isoformat()
    cultos = [{'chave': o.date, 'tipo': o.tipo, 'tema': o.tema, 'musicas': n_musicas.get(o.date, 0)}
              for o in Order.query.filter(Order.date >= hoje).order_by(Order.date)]
    cultos += [{'chave': o.date, 'tipo': o.tipo, 'tema': o.tema, 'musicas': n_musicas.get(o.date, 0), 'passado': True}
               for o in Order.query.filter(Order.date < hoje).order_by(Order.date.desc()).limit(30)]
    pastas = []
    base = paths.IMAGE_FOLDER
    nomes = ['Geral'] + (sorted(n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))) if os.path.isdir(base) else [])
    for nome in nomes:
        n = len(_arquivos_da_pasta(nome))
        if n:
            pastas.append({'nome': nome, 'arquivos': n})
    return jsonify({'musicas': musicas, 'cultos': cultos, 'pastas': pastas})


@pacote_bp.route('/api/pacote/exportar', methods=['POST'])
@login_required
def api_pacote_exportar():
    pedido = request.get_json(silent=True) or {}
    if not (pedido.get('musicas') or pedido.get('cultos') or pedido.get('pastas')):
        return jsonify({'error': 'Escolha ao menos uma música, culto ou pasta.'}), 400
    fd, caminho = tempfile.mkstemp(prefix='ucontrol-pacote-', suffix='.zip')
    os.close(fd)

    @after_this_request
    def _apagar(resposta):
        resposta.call_on_close(lambda: os.path.exists(caminho) and os.remove(caminho))
        return resposta

    criar_pacote(caminho, pedido.get('musicas') or [], pedido.get('cultos') or [], pedido.get('pastas') or [])
    nome = f'U-Control-pacote-{datetime.datetime.now().strftime("%Y-%m-%d_%H%M")}.zip'
    return send_file(caminho, as_attachment=True, download_name=nome, mimetype='application/zip')


@pacote_bp.route('/api/pacote/analisar', methods=['POST'])
@login_required
def api_pacote_analisar():
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify({'error': 'Escolha o arquivo do pacote.'}), 400
    token = uuid.uuid4().hex
    caminho = os.path.join(_pasta_temp(), token + '.zip')
    arquivo.save(caminho)
    try:
        resultado = analisar(caminho)
    except (PacoteInvalido, ValueError, KeyError) as e:
        os.remove(caminho)
        return jsonify({'error': str(e) if isinstance(e, PacoteInvalido) else 'Pacote danificado.'}), 400
    return jsonify({'token': token, **resultado})


@pacote_bp.route('/api/pacote/importar', methods=['POST'])
@login_required
def api_pacote_importar():
    pedido = request.get_json(silent=True) or {}
    token = pedido.get('token') or ''
    if not re.fullmatch(r'[0-9a-f]{32}', token):
        return jsonify({'error': 'Pacote não encontrado. Envie de novo.'}), 400
    caminho = os.path.join(_pasta_temp(), token + '.zip')
    if not os.path.exists(caminho):
        return jsonify({'error': 'Pacote não encontrado. Envie de novo.'}), 400
    try:
        feito = importar(caminho, pedido.get('escolhas') or {})
    except PacoteInvalido as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if os.path.exists(caminho):
            os.remove(caminho)
    return jsonify({'ok': True, **feito})
