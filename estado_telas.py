"""Quem cuida de cada tela sobrevive a um reinício do servidor.

Tudo isso vivia só na memória: se o Pi reiniciasse no meio do culto,
todo mundo voltava para "Nenhuma", o palco esquecia que estava na Bíblia
ou na Letra, e cada um tinha que escolher a tela e pôr o conteúdo de
novo (teste de 09/11). Aqui o estado vai para instance/telas.json a cada
ação que o muda e volta quando o servidor liga.

Guarda: o modo de cada aparelho (display_state._device_modes), os
responsáveis e o "acompanhar" de cada tela (destinos.py) e o que o palco
mostra (telao._monitor). O público já volta sozinho do banco
(telao._public_entry → DisplayState)."""
import json
import logging
import os
import time

_caminho = None
_ultimo = None
# Logo depois de ligar, os aparelhos ainda estão reconectando: ninguém
# perde a tela por "não ter aparelho conectado" nesse intervalo
CARENCIA_S = 120
_ligou_em = None

log = logging.getLogger('ucontrol')


def init_app(app):
    """Liga o arquivo e carrega o estado salvo. Nos testes não faz nada."""
    global _caminho
    if app.config.get('TESTING'):
        _caminho = None
        return
    _caminho = os.path.join(app.instance_path, 'telas.json')
    carregar()


def _foto():
    import destinos
    import display_state
    import telao
    return {
        'modos': dict(display_state._device_modes),
        'donos': dict(destinos._donos),
        'seguindo': dict(destinos._seguindo),
        'seguia_antes_do_preto': dict(destinos._seguia_antes_do_preto),
        'palco_na_biblia': destinos._palco_na_biblia,
        'palco_sem_cifra': destinos._palco_sem_cifra,
        'passagem': destinos._passagem,
        'ultimo_clicado': dict(destinos._ultimo_clicado),
        'monitor': telao._monitor,
    }


def salvar():
    """Grava se mudou desde a última vez. Nunca derruba a ação que chamou."""
    global _ultimo
    if not _caminho:
        return
    try:
        dados = _foto()
        texto = json.dumps(dados, ensure_ascii=False, sort_keys=True)
        if texto == _ultimo:
            return
        tmp = _caminho + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(texto)
        os.replace(tmp, _caminho)
        _ultimo = texto
    except Exception:
        log.exception('Falha ao salvar o estado das telas')


def carregar():
    global _ultimo, _ligou_em
    if not _caminho or not os.path.exists(_caminho):
        return
    try:
        with open(_caminho, encoding='utf-8') as f:
            texto = f.read()
        dados = json.loads(texto)
    except Exception:
        log.exception('Estado das telas ilegível; começando do zero')
        return
    import destinos
    import display_state
    import telao
    display_state._device_modes.update({k: v for k, v in (dados.get('modos') or {}).items()
                                        if v in ('all', 'public', 'monitor', 'none')})
    for t in destinos.TELAS:
        destinos._donos[t] = (dados.get('donos') or {}).get(t)
        destinos._seguindo[t] = bool((dados.get('seguindo') or {}).get(t, destinos._seguindo[t]))
        destinos._seguia_antes_do_preto[t] = bool((dados.get('seguia_antes_do_preto') or {}).get(t))
    destinos._palco_na_biblia = bool(dados.get('palco_na_biblia'))
    destinos._palco_sem_cifra = bool(dados.get('palco_sem_cifra'))
    destinos._passagem = dados.get('passagem')
    destinos._ultimo_clicado.clear()
    destinos._ultimo_clicado.update(dados.get('ultimo_clicado') or {})
    if isinstance(dados.get('monitor'), dict):
        telao._monitor = dados['monitor']
    _ultimo = texto
    _ligou_em = time.monotonic()
    log.info('Estado das telas recuperado: %s', destinos._donos)


def em_carencia():
    """Servidor acabou de ligar com estado recuperado?"""
    return _ligou_em is not None and time.monotonic() - _ligou_em < CARENCIA_S
