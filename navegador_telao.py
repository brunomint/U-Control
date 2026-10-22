"""Site no telão, como no Holyrics: um navegador de verdade (Chrome/Edge)
abre o site em tela cheia no monitor do telão, e o Controle comanda ele
pelo protocolo de depuração do próprio navegador (DevTools/CDP): teclas,
rolar, zoom, voltar, recarregar. Num quadro (iframe) da tela pública muitos
sites se recusam a abrir, e não dá pra rolar nem apertar teclas neles.

Só onde o U-Control roda com área de trabalho (instalação Windows; o
desktop.py registra o navegador e o monitor em desktop_ponte). Usa um
perfil próprio (UControl-site): login feito uma vez num site fica salvo.
Não precisa da janela em foco — o teclado do PC continua do operador."""
import json
import logging
import os
import re
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit

import desktop_ponte

ZOOM_MIN, ZOOM_MAX, ZOOM_PASSO = 0.5, 3.0, 0.15

_estado = {'proc': None, 'porta': None, 'zoom': 1.0}
_lock = threading.RLock()

# acao -> (key, code, windowsVirtualKeyCode, texto digitado)
_TECLAS = {
    'cima': ('ArrowUp', 'ArrowUp', 38, None),
    'baixo': ('ArrowDown', 'ArrowDown', 40, None),
    'esquerda': ('ArrowLeft', 'ArrowLeft', 37, None),
    'direita': ('ArrowRight', 'ArrowRight', 39, None),
    'pagina-cima': ('PageUp', 'PageUp', 33, None),
    'pagina-baixo': ('PageDown', 'PageDown', 34, None),
    'inicio': ('Home', 'Home', 36, None),
    'fim': ('End', 'End', 35, None),
    'enter': ('Enter', 'Enter', 13, '\r'),
    'espaco': (' ', 'Space', 32, ' '),
    'tab': ('Tab', 'Tab', 9, None),
}
# Muitos sites rolam um painel interno, não a janela: tecla "no vazio" e
# window.scrollBy não mexem nele. _ALVO acha a área que rola no meio da tela.
_ALVO = '''(() => {
  let el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  for (; el && el !== document.body && el !== document.documentElement; el = el.parentElement) {
    const s = getComputedStyle(el);
    if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
  }
  return document.scrollingElement || document.documentElement;
})()'''
# Teclas que rolam: se a página não usou a tecla (nada rolou), rola a área
_ROLAGEM = {'pagina-baixo': 'a.clientHeight * 0.9', 'pagina-cima': '-a.clientHeight * 0.9',
            'espaco': 'a.clientHeight * 0.9', 'fim': 'a.scrollHeight', 'inicio': '-a.scrollHeight'}
ACOES = tuple(_TECLAS) + ('rolar-cima', 'rolar-baixo', 'zoom-mais', 'zoom-menos', 'zoom-normal', 'voltar', 'recarregar')


class SiteErro(Exception):
    pass


def disponivel():
    return desktop_ponte.navegador() is not None


def normalizar(url):
    url = (url or '').strip()
    if not url:
        raise SiteErro('Digite o endereço do site.')
    esquema = re.match(r'^([a-z][a-z0-9+.-]*):(?!\d)', url, re.I)  # "site.com:8080" é porta, não esquema
    if esquema and esquema.group(1).lower() not in ('http', 'https'):
        raise SiteErro('Só endereços de site (http ou https).')
    if '://' not in url:
        url = 'https://' + url
    partes = urlsplit(url)
    if partes.scheme not in ('http', 'https') or not partes.netloc:
        raise SiteErro('Endereço inválido. Use algo como igreja.com.br ou https://...')
    return url


def aberto():
    with _lock:
        proc = _estado['proc']
        return bool(proc and proc.poll() is None)


# Conexão local ao navegador: sem proxy do sistema no meio
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _porta_do_arquivo(perfil):
    """Com --remote-debugging-port=0 o próprio navegador escolhe a porta e
    grava em <perfil>/DevToolsActivePort (1ª linha) — sem disputa de porta."""
    try:
        with open(os.path.join(perfil, 'DevToolsActivePort'), encoding='utf-8') as f:
            return int(f.readline().strip())
    except (OSError, ValueError):
        return None


def _json(caminho):
    with _LOCAL.open(f"http://127.0.0.1:{_estado['porta']}{caminho}", timeout=3) as r:
        return json.loads(r.read().decode())


def _pagina():
    """A aba do site (a janela --app tem uma só)."""
    for alvo in _json('/json/list'):
        if alvo.get('type') == 'page':
            return alvo
    raise SiteErro('A janela do site não respondeu.')


def _cdp(metodo, **params):
    from websockets.sync.client import connect
    alvo = _pagina()
    with connect(alvo['webSocketDebuggerUrl'], open_timeout=3, close_timeout=1, max_size=None) as ws:
        ws.send(json.dumps({'id': 1, 'method': metodo, 'params': params}))
        fim = time.time() + 5
        while time.time() < fim:
            msg = json.loads(ws.recv(timeout=5))
            if msg.get('id') == 1:
                if 'error' in msg:
                    raise SiteErro(msg['error'].get('message', 'erro no navegador'))
                return msg.get('result', {})
    raise SiteErro('O navegador do site não respondeu.')


def _aplicar_zoom():
    # zoom da página (CSS): o atalho Ctrl+ do navegador não chega por aqui
    _cdp('Runtime.evaluate', expression=f"document.documentElement.style.zoom = '{_estado['zoom']}'")


def abrir(url):
    """Abre o site no telão; com a janela já aberta, só troca o endereço."""
    url = normalizar(url)
    with _lock:
        if aberto():
            _cdp('Page.navigate', url=url)
            _estado['zoom'] = 1.0
            return estado()
        navegador = desktop_ponte.navegador()
        if not navegador:
            raise SiteErro('Site no telão só funciona no computador do U-Control (instalação Windows).')
        perfil = desktop_ponte.perfil_site()
        os.makedirs(perfil, exist_ok=True)
        try:  # de uma abertura anterior: não pode ser confundido com o novo
            os.remove(os.path.join(perfil, 'DevToolsActivePort'))
        except OSError:
            pass
        args = [navegador, '--remote-debugging-port=0', f'--user-data-dir={perfil}',
                '--no-first-run', '--no-default-browser-check', '--autoplay-policy=no-user-gesture-required',
                f'--app={url}']
        posicao = desktop_ponte.monitor_telao()
        if posicao:
            args += [f'--window-position={posicao[0]},{posicao[1]}', '--start-fullscreen']
        else:
            args += ['--window-size=1280,720']  # um monitor só: janela comum, não cobre o Controle
        _estado.update(proc=subprocess.Popen(args), porta=None, zoom=1.0)
        fim = time.time() + 45  # 1ª vez com perfil novo pode demorar
        erro = None
        while time.time() < fim:
            _estado['porta'] = _estado['porta'] or _porta_do_arquivo(perfil)
            if _estado['porta']:
                try:
                    _pagina()
                    break
                except Exception as e:
                    erro = e
            if _estado['proc'].poll() is not None and not _estado['porta']:
                raise SiteErro(f'O navegador fechou ao abrir o site ({os.path.basename(navegador)}).')
            time.sleep(0.3)
        else:
            detalhe = (f"porta {_estado['porta']}, último erro: {erro!r}" if _estado['porta']
                       else 'o navegador não informou a porta de controle')
            logging.getLogger('ucontrol').error('Site no telão: %s não respondeu (%s)', navegador, detalhe)
            fechar()
            raise SiteErro(f'O navegador demorou demais pra abrir ({detalhe}).')
        logging.getLogger('ucontrol').info('Site no telão: %s', url)
        return estado()


def comando(acao):
    if acao not in ACOES:
        raise SiteErro(f'Comando desconhecido: {acao}')
    with _lock:
        if not aberto():
            raise SiteErro('Nenhum site aberto no telão.')
        if acao in _TECLAS:
            key, code, vk, texto = _TECLAS[acao]
            base = {'key': key, 'code': code, 'windowsVirtualKeyCode': vk, 'nativeVirtualKeyCode': vk}
            if acao in _ROLAGEM:
                _cdp('Runtime.evaluate', expression=f'window.__ucAlvo = {_ALVO}; window.__ucAntes = window.__ucAlvo.scrollTop + scrollY')
            _cdp('Input.dispatchKeyEvent', type='keyDown' if texto else 'rawKeyDown', **base, **({'text': texto} if texto else {}))
            _cdp('Input.dispatchKeyEvent', type='keyUp', **base)
            if acao in _ROLAGEM:
                time.sleep(0.25)
                _cdp('Runtime.evaluate', expression=(
                    '(() => { const a = window.__ucAlvo; if (a && a.isConnected && a.scrollTop + scrollY === window.__ucAntes) '
                    f'a.scrollBy({{top: {_ROLAGEM[acao]}, behavior: "smooth"}}); }})()'))
        elif acao in ('rolar-cima', 'rolar-baixo'):
            sinal = -1 if acao == 'rolar-cima' else 1
            _cdp('Runtime.evaluate', expression=f'{_ALVO}.scrollBy({{top: {sinal} * innerHeight * 0.3, behavior: "smooth"}})')
        elif acao.startswith('zoom'):
            z = 1.0 if acao == 'zoom-normal' else _estado['zoom'] + (ZOOM_PASSO if acao == 'zoom-mais' else -ZOOM_PASSO)
            _estado['zoom'] = round(min(ZOOM_MAX, max(ZOOM_MIN, z)), 2)
            _aplicar_zoom()
        elif acao == 'voltar':
            _cdp('Runtime.evaluate', expression='history.back()')
        elif acao == 'recarregar':
            _cdp('Page.reload')
        return estado()


def fechar():
    with _lock:
        proc = _estado['proc']
        _estado.update(proc=None, porta=None, zoom=1.0)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def estado():
    if not aberto():
        return {'disponivel': disponivel(), 'aberto': False}
    info = {'disponivel': True, 'aberto': True, 'zoom': _estado['zoom']}
    try:
        pagina = _pagina()
        info.update(url=pagina.get('url'), titulo=pagina.get('title'))
    except Exception:
        pass
    return info
