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


_DIVISAO = re.compile(r'^[ \t]*\|\|[ \t\r]*$')   # \r: letra colada do Windows


def sem_divisao(texto):
    """Tira as linhas "||" (divisão de slide só do telão do público)."""
    if not texto or not isinstance(texto, str):
        return texto
    return '\n'.join(l for l in re.split(r'\r?\n', texto) if not _DIVISAO.match(l))


_REPETICAO = re.compile(r'(^|\s)(?:/:|:/)(?:\s+|$)')
_SO_REPETICAO = re.compile(r'^\s*(?:(?:/:|:/)\s*)+$')


def sem_repeticao(texto):
    """Tira os sinais de repetição "/:" e ":/" (bis), que são para os músicos:
    o telão do público mostra só a letra. Mesma regra de UcFormato.semRepeticao."""
    if not texto or not isinstance(texto, str):
        return texto
    saida = []
    for linha in re.split(r'\r?\n', texto):
        if _SO_REPETICAO.match(linha):
            continue
        limpa = _REPETICAO.sub(r'\1', linha)
        saida.append(linha if limpa == linha else limpa.strip())
    return '\n'.join(saida)


def musica_sem_formato(song):
    """Cópia da música (dict de songs_store) com a letra sem as marcações e sem as linhas "||"."""
    if not song:
        return song
    song = copy.deepcopy(song)
    for secao in song.get('sections') or []:
        secao['text'] = [sem_divisao(limpar(t)) for t in (secao.get('text') or [])]
    return song
