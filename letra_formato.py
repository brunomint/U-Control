"""Tira as marcações de formatação da letra (static/js/letra_formato.js) para
as telas que não formatam: visualização da música e impressão. Mesmas regras
do JS: **negrito**, *itálico*, {cor}texto{/} e {tamanho}texto{/}."""
import copy
import re

CORES = ('amarelo', 'dourado', 'vermelho', 'laranja', 'verde', 'azul', 'roxo', 'rosa', 'branco', 'preto', 'cinza')
TAMANHOS = ('grande', 'maior', 'pequeno')
_BLOCO = re.compile(r'\{(#[0-9a-fA-F]{6}|[a-zA-Z]+)\}([^{]*?)\{/\}')
_NEGRITO = re.compile(r'\*\*(\S(?:[^\n]*?\S)?)\*\*')
_ITALICO = re.compile(r'\*(\S(?:[^\n*]*?\S)?)\*')


def _conhecido(nome):
    return nome.startswith('#') or nome.lower() in CORES or nome.lower() in TAMANHOS


def limpar(texto):
    if not texto or not isinstance(texto, str):
        return texto
    antes = None
    while antes != texto:
        antes = texto
        texto = _BLOCO.sub(lambda m: m.group(2) if _conhecido(m.group(1)) else m.group(0), texto)
    return _ITALICO.sub(r'\1', _NEGRITO.sub(r'\1', texto))


def musica_sem_formato(song):
    """Cópia da música (dict de songs_store) com a letra sem as marcações."""
    if not song:
        return song
    song = copy.deepcopy(song)
    for secao in song.get('sections') or []:
        secao['text'] = [limpar(t) for t in (secao.get('text') or [])]
    return song
