"""Aviso de versão nova, no estilo do Holyrics: compara o arquivo VERSION
com a última Release do GitHub (brunomint/U-Control, público).

Vale pra todo tipo de instalação; o que muda é como atualizar
(install_kind): no Windows o próprio programa baixa e roda o instalador
novo; no Pi/Linux é o scripts/deploy.py; no Docker, o compose.

A consulta roda em segundo plano e fica guardada (CACHE_OK) — a página
nunca espera o GitHub, e sem internet (culto offline) não acontece nada."""
import hashlib
import logging
import os
import subprocess
import sys
import threading
import time

import requests

import paths

logger = logging.getLogger('ucontrol')

REPO = 'brunomint/U-Control'
API_URL = f'https://api.github.com/repos/{REPO}/releases/latest'
DOWNLOAD_PREFIX = f'https://github.com/{REPO}/releases/download/'
CACHE_OK = 6 * 3600
CACHE_ERRO = 30 * 60

_lock = threading.Lock()
# consultado: o GitHub respondeu (mesmo que sem Release nenhuma ainda)
_cache = {'release': None, 'quando': 0.0, 'buscando': False, 'consultado': False}
# Download/instalação no Windows: estado lido pela página /atualizacao
# libreoffice: este download é o do botão "Instalar LibreOffice"
_instalacao = {'estado': None, 'progresso': 0, 'erro': None, 'libreoffice': False}


def current_version():
    try:
        with open(os.path.join(paths.APP_DIR, 'VERSION'), encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return '0.0.0'


def install_kind():
    if getattr(sys, 'frozen', False):
        return 'windows'
    if os.path.exists('/.dockerenv'):
        return 'docker'
    return 'servidor'


def parse_version(texto):
    """'v1.10.2' -> (1, 10, 2). Texto estranho vira (0,), que nunca é
    'mais nova'."""
    try:
        return tuple(int(p) for p in (texto or '').strip().lstrip('vV').split('.'))
    except ValueError:
        return (0,)


def _fetch_latest():
    r = requests.get(API_URL, timeout=8, headers={'Accept': 'application/vnd.github+json'})
    if r.status_code == 404:  # repositório sem nenhuma Release ainda
        return None
    r.raise_for_status()
    dados = r.json()
    instalador = next((a for a in dados.get('assets', [])
                       if a.get('name', '').lower().endswith('.exe')), None)
    return {
        'version': (dados.get('tag_name') or '').lstrip('vV'),
        'notes': dados.get('body') or '',
        'url': dados.get('html_url'),
        'published_at': dados.get('published_at'),
        'installer': instalador and {
            'name': instalador['name'],
            'url': instalador['browser_download_url'],
            'size': instalador.get('size'),
            # "sha256:<hex>" (GitHub calcula pra cada arquivo da Release)
            'digest': instalador.get('digest'),
        },
    }


def _buscar():
    try:
        release = _fetch_latest()
        validade, consultado = CACHE_OK, True
    except Exception as e:  # sem internet, GitHub fora, limite da API
        logger.info('Atualização: não deu pra consultar o GitHub (%s)', e)
        release, validade, consultado = _cache['release'], CACHE_ERRO, False
    with _lock:
        _cache['release'] = release
        _cache['consultado'] = consultado or _cache['consultado']
        _cache['quando'] = time.time() - (CACHE_OK - validade)
        _cache['buscando'] = False


def latest_release():
    """Última Release conhecida (pode ser None). Se a guardada venceu,
    dispara uma busca em segundo plano e devolve a que tem."""
    with _lock:
        vencida = time.time() - _cache['quando'] > CACHE_OK
        if vencida and not _cache['buscando'] and os.getenv('UCONTROL_TESTING') != '1':
            _cache['buscando'] = True
            threading.Thread(target=_buscar, daemon=True).start()
        return _cache['release']


def status(local=False, tem_libreoffice=True):
    """O que a página /atualizacao e o selo da barra mostram. local=True
    quando quem pede está no próprio computador do U-Control;
    tem_libreoffice: achou o LibreOffice (blueprints/gallery.py)."""
    release = latest_release()
    atual = current_version()
    disponivel = bool(release) and parse_version(release['version']) > parse_version(atual)
    kind = install_kind()
    return {
        'current': atual,
        'checked': _cache['consultado'] or release is not None,
        'checking': _cache['buscando'],
        'latest': release and release['version'],
        'available': disponivel,
        'kind': kind,
        'notes': release['notes'] if disponivel else '',
        'release_url': release and release['url'],
        'can_install': disponivel and kind == 'windows' and local and bool(release.get('installer')),
        'install': dict(_instalacao),
        # Windows sem LibreOffice: PowerPoint não vira slide. Quem instalou
        # a 1.0.0, desmarcou a opção ou teve o download falhando ficava sem,
        # e a atualização pelo programa nunca baixa (ver _baixar_e_instalar)
        'libreoffice': tem_libreoffice,
        'can_install_libreoffice': (kind == 'windows' and local and not tem_libreoffice
                                    and bool(release) and bool(release.get('installer'))),
    }


# --- Windows: baixar e rodar o instalador -----------------------------------

def _baixar_e_instalar(instalador, libreoffice=False):
    pasta = os.path.join(paths.DATA_DIR or paths.APP_DIR, 'atualizacoes')
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, os.path.basename(instalador['name']))
    try:
        sha = hashlib.sha256()
        baixado = 0
        total = instalador.get('size') or 0
        with requests.get(instalador['url'], stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(destino + '.part', 'wb') as f:
                for bloco in r.iter_content(1 << 20):
                    f.write(bloco)
                    sha.update(bloco)
                    baixado += len(bloco)
                    if total:
                        _instalacao['progresso'] = int(baixado * 100 / total)
        esperado = (instalador.get('digest') or '').partition('sha256:')[2]
        if esperado and sha.hexdigest() != esperado:
            raise ValueError('arquivo baixado não confere (SHA-256)')
        os.replace(destino + '.part', destino)
    except Exception as e:
        logger.exception('Atualização: download falhou')
        _instalacao.update(estado='erro', erro=str(e))
        return
    _instalacao.update(estado='instalando', progresso=100)
    logger.info('Atualização: rodando %s', destino)
    # O instalador fecha o U-Control (CloseApplications), troca os arquivos
    # e, com /RELAUNCH, abre de novo (ver windows/ucontrol.iss). Se a
    # pessoa recusar a permissão de administrador, nada muda.
    # !libreoffice: atualização nunca baixa os 360 MB do LibreOffice; só o
    # botão "Instalar LibreOffice" liga essa opção do instalador
    # (windows/ucontrol.iss — ela some sozinha se o LibreOffice já existe)
    tarefa = '/MERGETASKS=libreoffice' if libreoffice else '/MERGETASKS=!libreoffice'
    subprocess.Popen([destino, '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/RELAUNCH',
                      tarefa], close_fds=True)


def start_install(libreoffice=False):
    """Começa a baixar o instalador da última versão. Retorna mensagem de
    erro, ou None se começou. libreoffice=True: o mesmo instalador, com a
    opção de baixar e instalar o LibreOffice — vale mesmo sem versão nova
    (reinstala a mesma por cima, sem apagar nada)."""
    if install_kind() != 'windows':
        return 'Atualização automática só no programa do Windows.'
    if _instalacao['estado'] in ('baixando', 'instalando'):
        return None
    release = latest_release()
    if not release:
        return 'Não deu pra consultar o GitHub. Confira a internet deste computador.'
    if not libreoffice and parse_version(release['version']) <= parse_version(current_version()):
        return 'Não há versão nova.'
    instalador = release.get('installer')
    if not instalador or not instalador['url'].startswith(DOWNLOAD_PREFIX):
        return 'Esta versão não tem instalador para Windows.'
    _instalacao.update(estado='baixando', progresso=0, erro=None, libreoffice=libreoffice)
    threading.Thread(target=_baixar_e_instalar, args=(instalador, libreoffice), daemon=True).start()
    return None
