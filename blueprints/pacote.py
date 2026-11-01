"""Levar músicas, cultos e fotos de um U-Control pra outro, somando ao que
já existe (o backup, em blueprints/backup.py, troca tudo). Caso típico:
preparar o culto em casa e levar pro PC da igreja.

Pacote = .zip com:
    manifest.json   {'app': 'U-Control', 'tipo': 'pacote', ...}
    pacote.json     {'musicas': [...], 'cultos': {chave: ordem}, 'pastas': [...],
                     'temas': [...], 'avulsos': ['Fundos/ceu.mp4', ...]}
    imagens/<pasta>/<arquivo>   fotos, slides (e a versão animada) e vídeos

Temas do telão (temas_store.py) vão junto: os escolhidos, os das músicas e
dos cultos do pacote, e as imagens/vídeos de fundo que eles usam
("avulsos", um arquivo só de uma pasta). Aqui, tema com o mesmo nome é o
mesmo tema; o id muda e as músicas/cultos são reescritos pro id daqui.
Pacote com tema é formato 2 (versões antigas pedem pra atualizar).

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
from i18n import gettext as tr
import temas_store
from orders_store import get_order, save_order
from songs_store import chave_musica, get_song, musicas_por_chave, next_song_id, save_song

pacote_bp = Blueprint('pacote', __name__)

FORMATO = 2   # 2: temas do telão e arquivos avulsos
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


# --- Temas e arquivos de fundo ------------------------------------------

def _urls_de_fundo(theme):
    """Endereços /static/imagens/... usados num tema de música (fundo solto e
    fundos por parte) ou num fundo de tema salvo."""
    if not isinstance(theme, dict):
        return []
    urls = [theme.get('url')] + [f.get('url') for f in (theme.get('secoes') or {}).values() if isinstance(f, dict)]
    return [u for u in urls if isinstance(u, str) and u.startswith('/static/imagens/')]


def _avulso(url):
    """'/static/imagens/Fundos/a.mp4' -> 'Fundos/a.mp4'; na raiz -> 'Geral/a.jpg'; None se não existir."""
    partes = url[len('/static/imagens/'):].split('/')
    pasta, arq = (('Geral', partes[0]) if len(partes) == 1 else (partes[0], partes[1]) if len(partes) == 2 else (None, None))
    if not pasta or arq in ('', '.', '..') or not _pasta_dir(pasta):
        return None
    return f'{pasta}/{arq}' if os.path.isfile(os.path.join(_pasta_dir(pasta), arq)) else None


def _id_tema(theme):
    return theme.get('tema_id') if isinstance(theme, dict) else None


def _com_tema(theme, ids_temas):
    """Song.theme com o tema_id trocado pro id daqui (ids_temas: ref -> id)."""
    if not isinstance(theme, dict) or not theme.get('tema_id'):
        return theme
    novo = ids_temas.get(int(theme['tema_id']))
    theme = dict(theme)
    if novo:
        theme['tema_id'] = novo
    else:
        theme.pop('tema_id')
    return theme or None


def _conteudo_tema(t):
    return json.dumps(temas_store.normalizar(t), sort_keys=True, ensure_ascii=False)


def _temas_daqui():
    return {t['nome'].strip().lower(): t for t in temas_store.listar()}


# --- Exportar -------------------------------------------------------------

def criar_pacote(destino, musicas=(), cultos=(), pastas=(), temas=()):
    ids = {int(i) for i in musicas}
    ids_temas = {int(i) for i in temas}
    dados_cultos = {}
    for chave in cultos:
        ordem = get_order(chave)
        if not ordem:
            continue
        dados_cultos[chave] = ordem
        if ordem.get('tema_telao'):
            ids_temas.add(int(ordem['tema_telao']))
        for item in ordem.get('itens', []):  # o culto leva as músicas dele
            m = _RE_LYRICS.match(item.get('url') or '')
            if m:
                ids.add(int(m.group(1)))
    dados_musicas = [s for s in (get_song(i) for i in sorted(ids)) if s]
    for s in dados_musicas:
        s.pop('last_played', None)
        if _id_tema(s.get('theme')):
            ids_temas.add(int(_id_tema(s['theme'])))
    dados_temas = [t for t in (temas_store.obter(i) for i in sorted(ids_temas)) if t]

    pastas = [p for p in pastas if _pasta_dir(p)]
    urls = [u for s in dados_musicas for u in _urls_de_fundo(s.get('theme'))] + \
           [u for t in dados_temas for u in _urls_de_fundo(t['fundo'])]
    avulsos = sorted({a for a in map(_avulso, urls) if a and a.split('/')[0] not in pastas})
    formato = FORMATO if (dados_temas or avulsos) else 1
    manifest = {'app': 'U-Control', 'tipo': 'pacote', 'formato': formato,
                'versao': updates.current_version(),
                'criado': datetime.datetime.now().isoformat(timespec='seconds')}
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr('pacote.json', json.dumps(
            {'musicas': dados_musicas, 'cultos': dados_cultos, 'pastas': pastas,
             'temas': dados_temas, 'avulsos': avulsos}, ensure_ascii=False))
        for nome in pastas:
            for arq in _arquivos_da_pasta(nome):
                zf.write(os.path.join(_pasta_dir(nome), arq), f'imagens/{nome}/{arq}',
                         compress_type=zipfile.ZIP_STORED)
        for caminho in avulsos:
            pasta, arq = caminho.split('/')
            zf.write(os.path.join(_pasta_dir(pasta), arq), f'imagens/{caminho}', compress_type=zipfile.ZIP_STORED)
    return {'musicas': len(dados_musicas), 'cultos': len(dados_cultos), 'pastas': len(pastas), 'temas': len(dados_temas)}


# --- Importar -------------------------------------------------------------

def _reescrever_ordem(ordem, ids, ids_temas=None):
    """Itens /lyrics/<id do pacote> -> /lyrics/<id daqui> (ids: ref -> id);
    tema do telão do culto -> o id daqui (ids_temas)."""
    def url(u):
        m = _RE_LYRICS.match(u or '')
        if m and ids.get(int(m.group(1))) is not None:
            return f'/lyrics/{ids[int(m.group(1))]}' + u[m.end():]
        return u
    ordem = dict(ordem)
    ordem['itens'] = [dict(i, url=url(i['url'])) if i.get('url') else i for i in ordem.get('itens', [])]
    if ordem.get('tema_telao') and ids_temas is not None:
        novo = ids_temas.get(int(ordem['tema_telao']))
        if novo:
            ordem['tema_telao'] = novo
        else:
            ordem.pop('tema_telao')
    return ordem


def _sem_feitos(ordem):
    return json.dumps(ordem, sort_keys=True, ensure_ascii=False)


class PacoteInvalido(Exception):
    pass


def ler_pacote(caminho):
    if not zipfile.is_zipfile(caminho):
        raise PacoteInvalido(tr('Este arquivo não é um pacote do U-Control.'))
    with zipfile.ZipFile(caminho) as zf:
        try:
            manifest = json.loads(zf.read('manifest.json'))
        except (KeyError, ValueError):
            raise PacoteInvalido(tr('Este arquivo não é um pacote do U-Control.'))
        if manifest.get('app') != 'U-Control':
            raise PacoteInvalido(tr('Este arquivo não é um pacote do U-Control.'))
        if manifest.get('tipo') != 'pacote':
            raise PacoteInvalido(tr('Este arquivo é um backup completo: restaure em Sistema → Backup.'))
        if manifest.get('formato', 0) > FORMATO:
            raise PacoteInvalido(tr('Pacote de uma versão mais nova do U-Control. Atualize este antes de importar.'))
        dados = json.loads(zf.read('pacote.json'))
        avulsos = set(dados.get('avulsos') or [])
        arquivos = {}
        for nome in zf.namelist():
            if nome in ('manifest.json', 'pacote.json') or nome.endswith('/'):
                continue
            partes = nome.split('/')
            if len(partes) != 3 or partes[0] != 'imagens' \
                    or (partes[1] not in dados.get('pastas', []) and f'{partes[1]}/{partes[2]}' not in avulsos) \
                    or partes[2] in ('', '.', '..') or '\\' in nome or partes[1] in ('.', '..', ''):
                raise PacoteInvalido(tr('Arquivo estranho dentro do pacote: {nome}', nome=nome))
            arquivos.setdefault(partes[1], []).append((partes[2], zf.getinfo(nome).file_size))
    return manifest, dados, arquivos


def analisar(caminho):
    manifest, dados, arquivos = ler_pacote(caminho)
    temas_aqui = _temas_daqui()
    temas = []
    ids_temas = {}   # tema do pacote -> o de mesmo nome daqui (pra comparar músicas e cultos)
    for t in dados.get('temas', []):
        existente = temas_aqui.get(str(t.get('nome') or '').strip().lower())
        status = 'novo'
        if existente:
            ids_temas[t['id']] = existente['id']
            status = 'igual' if _conteudo_tema(existente) == _conteudo_tema(t) else 'diferente'
        temas.append({'ref': t['id'], 'nome': t.get('nome'), 'status': status})
    daqui = _musicas_daqui()
    musicas = []
    for s in dados.get('musicas', []):
        existente = daqui.get(_chave(s.get('title'), s.get('author')))
        status = 'nova'
        if existente is not None:
            status = 'igual' if _conteudo(get_song(existente) or {}) == _conteudo({**s, 'theme': _com_tema(s.get('theme'), ids_temas)}) else 'diferente'
        musicas.append({'ref': s['id'], 'title': s.get('title'), 'author': s.get('author'), 'status': status})
    # Pra comparar culto, os links /lyrics/<id do pacote> viram os ids daqui
    ids = {m['ref']: daqui.get(_chave(m['title'], m['author'])) for m in musicas}
    cultos = []
    for chave, ordem in dados.get('cultos', {}).items():
        atual = get_order(chave)
        status = 'novo'
        if atual:
            status = 'igual' if _sem_feitos(atual) == _sem_feitos(_reescrever_ordem(ordem, ids, ids_temas)) else 'diferente'
        cultos.append({'chave': chave, 'tipo': ordem.get('tipo'), 'tema': ordem.get('tema'), 'status': status})
    pastas = []
    for nome in dados.get('pastas', []):
        aqui = set(_arquivos_da_pasta(nome)) if _pasta_dir(nome) else set()
        lista = arquivos.get(nome, [])
        pastas.append({'nome': nome, 'arquivos': len(lista), 'ja_existem': sum(1 for a, _ in lista if a in aqui)})
    return {'manifest': manifest, 'musicas': musicas, 'cultos': cultos, 'pastas': pastas, 'temas': temas,
            'avulsos': len(dados.get('avulsos') or [])}


def importar(caminho, escolhas):
    """escolhas: {'musicas': {ref: 'pacote'|'daqui'}, 'cultos': {chave: ...}}.
    Sem escolha, fica a do pacote (é o que a pessoa trouxe pra usar)."""
    _, dados, _ = ler_pacote(caminho)
    esc_m = {str(k): v for k, v in (escolhas.get('musicas') or {}).items()}
    esc_c = escolhas.get('cultos') or {}
    esc_t = {str(k): v for k, v in (escolhas.get('temas') or {}).items()}
    daqui = _musicas_daqui()
    novo_id = {}
    feito = {'musicas_novas': 0, 'musicas_atualizadas': 0, 'cultos': 0, 'arquivos': 0, 'temas': 0}

    # Temas primeiro: músicas e cultos apontam pra eles
    temas_aqui = _temas_daqui()
    ids_temas = {}
    for t in dados.get('temas', []):
        if not isinstance(t, dict) or not str(t.get('nome') or '').strip() or not isinstance(t.get('id'), int):
            continue
        existente = temas_aqui.get(str(t.get('nome') or '').strip().lower())
        if existente is None:
            novo = temas_store.salvar(t.get('nome'), t)
            ids_temas[t['id']] = novo['id']
            temas_aqui[novo['nome'].strip().lower()] = novo
            feito['temas'] += 1
            continue
        ids_temas[t['id']] = existente['id']
        if esc_t.get(str(t['id']), 'pacote') == 'pacote' and _conteudo_tema(existente) != _conteudo_tema(t):
            temas_store.salvar(existente['nome'], t, existente['id'])
            feito['temas'] += 1

    for s in dados.get('musicas', []):
        ref = s['id']
        s = {**s, 'theme': _com_tema(s.get('theme'), ids_temas)}
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
        save_order(chave, _reescrever_ordem(ordem, novo_id, ids_temas))
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
        # Imagens e vídeos de fundo dos temas (um arquivo de uma pasta, sem levar a pasta inteira)
        for caminho in dados.get('avulsos') or []:
            pasta_nome, arq = caminho.split('/', 1)
            if '/' in arq or arq in ('', '.', '..') or pasta_nome.startswith('.') or not _pasta_dir(pasta_nome):
                continue
            pasta = _pasta_dir(pasta_nome)
            os.makedirs(pasta, exist_ok=True)
            alvo = os.path.join(pasta, arq)
            try:
                info = zf.getinfo(f'imagens/{caminho}')
            except KeyError:
                continue
            with zf.open(info) as src, open(alvo + '.importando', 'wb') as dst:
                shutil.copyfileobj(src, dst)
            os.replace(alvo + '.importando', alvo)
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
    temas = [{'id': t['id'], 'nome': t['nome']} for t in temas_store.listar()]
    return jsonify({'musicas': musicas, 'cultos': cultos, 'pastas': pastas, 'temas': temas})


@pacote_bp.route('/api/pacote/exportar', methods=['POST'])
@login_required
def api_pacote_exportar():
    pedido = request.get_json(silent=True) or {}
    if not (pedido.get('musicas') or pedido.get('cultos') or pedido.get('pastas') or pedido.get('temas')):
        return jsonify({'error': tr('Escolha ao menos uma música, culto, pasta ou tema.')}), 400
    fd, caminho = tempfile.mkstemp(prefix='ucontrol-pacote-', suffix='.zip')
    os.close(fd)

    @after_this_request
    def _apagar(resposta):
        resposta.call_on_close(lambda: os.path.exists(caminho) and os.remove(caminho))
        return resposta

    criar_pacote(caminho, pedido.get('musicas') or [], pedido.get('cultos') or [], pedido.get('pastas') or [],
                 pedido.get('temas') or [])
    nome = f'U-Control-pacote-{datetime.datetime.now().strftime("%Y-%m-%d_%H%M")}.zip'
    return send_file(caminho, as_attachment=True, download_name=nome, mimetype='application/zip')


@pacote_bp.route('/api/pacote/analisar', methods=['POST'])
@login_required
def api_pacote_analisar():
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify({'error': tr('Escolha o arquivo do pacote.')}), 400
    token = uuid.uuid4().hex
    caminho = os.path.join(_pasta_temp(), token + '.zip')
    arquivo.save(caminho)
    try:
        resultado = analisar(caminho)
    except (PacoteInvalido, ValueError, KeyError) as e:
        os.remove(caminho)
        return jsonify({'error': str(e) if isinstance(e, PacoteInvalido) else tr('Pacote danificado.')}), 400
    return jsonify({'token': token, **resultado})


@pacote_bp.route('/api/pacote/importar', methods=['POST'])
@login_required
def api_pacote_importar():
    pedido = request.get_json(silent=True) or {}
    token = pedido.get('token') or ''
    if not re.fullmatch(r'[0-9a-f]{32}', token):
        return jsonify({'error': tr('Pacote não encontrado. Envie de novo.')}), 400
    caminho = os.path.join(_pasta_temp(), token + '.zip')
    if not os.path.exists(caminho):
        return jsonify({'error': tr('Pacote não encontrado. Envie de novo.')}), 400
    try:
        feito = importar(caminho, pedido.get('escolhas') or {})
    except PacoteInvalido as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if os.path.exists(caminho):
            os.remove(caminho)
    return jsonify({'ok': True, **feito})
