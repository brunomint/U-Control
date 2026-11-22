"""Cifras da versão simples (/lite/cifras e /lite/cifra/<id>, Fase 1B de
docs/PLANO-LITE.md): a ordem do culto e a cifra de cada música montadas no
servidor, para navegador antigo. Tom e Capo viram links (?tom=, ?capo=),
sem JavaScript. A cifra sai das mesmas funções do PDF de impressão
(chord_lines.secoes_cifra), que seguem a lógica de static/js/chord_lines.js."""
import re
from datetime import date

from chord_lines import CHORD_MAP, describe_key, first_chord_token, secoes_cifra, transpose_chord

# Os 12 tons como na grade do Tom de /view/<id>
TONS = ['A', 'Bb', 'B', 'C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab']
_MUSICA = re.compile(r'^/lyrics/(\d+)')


def numero(valor, minimo, maximo):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return 0


def normal(semitons):
    """-5..6: o caminho mais curto, como o jumpToKey do /view."""
    s = semitons % 12
    return s - 12 if s > 6 else s


def itens_da_ordem(ordem):
    """Itens para a lista: {'tipo': 'musica'|'biblia'|'texto', 'titulo', 'autor', 'id'}."""
    saida = []
    for item in ordem.get('itens') or []:
        m = _MUSICA.match(item.get('url') or '')
        if item.get('isBible'):
            saida.append({'tipo': 'biblia', 'titulo': item.get('reference') or ''})
        elif m:
            titulo, _, autor = (item.get('title') or '').partition(' | ')
            saida.append({'tipo': 'musica', 'id': int(m.group(1)), 'titulo': titulo.strip(), 'autor': autor.strip()})
        elif item.get('anyText') or item.get('title'):
            saida.append({'tipo': 'texto', 'titulo': item.get('anyText') or item.get('title')})
    return saida


def escolher_ordem(chave):
    """(chave, ordem, outros cultos). Sem chave: o próximo culto a partir de hoje."""
    import orders_store
    hoje = date.today().isoformat()
    proximos = orders_store.proximos_cultos(hoje)
    if chave and orders_store.KEY_RE.match(chave):
        return chave, orders_store.get_order(chave), proximos
    if proximos:
        return proximos[0][0], proximos[0][1], proximos
    return None, {}, proximos


def vizinhas(ordem, song_id):
    """(anterior, próxima) música da ordem, ou None."""
    ids = [i['id'] for i in itens_da_ordem(ordem) if i['tipo'] == 'musica']
    if song_id not in ids:
        return None, None
    i = ids.index(song_id)
    return (ids[i - 1] if i > 0 else None), (ids[i + 1] if i + 1 < len(ids) else None)


def montar_cifra(song, tom, capo):
    """Tudo o que a página da cifra mostra. `song` já na Ordem no culto e sem
    marcações (songs_store.musica_na_ordem + letra_formato.musica_sem_formato).
    tom: semitons a partir do original (o som); capo: casa do capotraste
    (os acordes saem `capo` semitons abaixo — as formas que o violão toca)."""
    secoes = secoes_cifra(song.get('sections') or [], tom - capo,
                          nota_partitura='(partitura: só aparece na página normal)')
    primeiro = first_chord_token([s['texto'] for s in secoes_cifra(song.get('sections') or [], 0)])
    soa = transpose_chord(primeiro, tom) if primeiro else None
    tom_atual = describe_key(soa) if soa else None
    raiz = tom_atual[:-1] if tom_atual and tom_atual.endswith('m') else tom_atual

    grade = []
    for t in TONS:
        if raiz in CHORD_MAP:
            delta = normal(CHORD_MAP[t] - CHORD_MAP[raiz])
            grade.append({'tom': t, 'semitons': normal(tom + delta), 'atual': delta == 0})
    return {
        'secoes': secoes,
        'tom_atual': tom_atual,
        'grade': grade,
        'formas': describe_key(transpose_chord(soa, -capo)) if soa and capo else None,
        'tem_partitura': any(s['sem_partitura'] or 'sem-partitura' in s['html'] for s in secoes),
    }
