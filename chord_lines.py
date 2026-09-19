"""Porta em Python de static/js/chord_lines.js — só o necessário pra
gerar o HTML de impressão em blueprints/print_song.py (WeasyPrint não
roda JavaScript, então o realce/transposição de acordes que
static/js/chord_lines.js faz no navegador precisa acontecer aqui,
server-side, antes de virar PDF).

Mantém a MESMA lógica do arquivo JS de propósito — qualquer correção
feita lá (ex: o achado real sobre barras de compasso "|") também deve
ser replicada aqui pra não dessincronizar o texto exibido na tela do
que sai impresso. Ver o comentário no topo do .js pra contexto completo
(classificação por linha inteira, estilo Quelea)."""
import html
import re

CHORD_MAP = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5,
    'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11,
}

# Mistura sustenido/bemol por nota, mesma convenção do .js.
CHORD_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

CHORD_TOKEN_REGEX = re.compile(
    r'^[A-G][#b]?(?:m|min|maj|M|sus|dim|aug|add)?[0-9]*(?:M)?(?:º)?(?:\([0-9]+\))?(?:/[A-G][#b]?)?$'
)

_CHORD_BASE_REGEX = re.compile(r'^([A-G][#b]?)(.*)$')
_BASS_REGEX = re.compile(r'(/)([A-G][#b]?)')

# Acorde isolado entre barras de compasso, fora de linha de cifra
# (ex.: "algumas palavras | A | mais palavras") — mesmo regex de
# renderChords() em view_song.html.
_BARLINE_CHORD_REGEX = re.compile(
    r'\|\s*([A-G][#b]?(?:m|min|maj|M|sus|dim|aug|add|°|º)?(?:7M|7|9|11|13|6)?[0-9]*\+?(?:/[A-G][#b]?)?)\s*\|'
)


def transpose_chord(chord, semitones):
    match = _CHORD_BASE_REGEX.match(chord)
    if not match:
        return chord
    base_note, modifiers = match.group(1), match.group(2)
    base_index = CHORD_MAP.get(base_note)
    if base_index is None:
        return chord
    new_index = (base_index + semitones) % 12
    transposed_base = CHORD_NAMES[new_index]

    def _bass_sub(m):
        bass_index = CHORD_MAP.get(m.group(2))
        if bass_index is None:
            return m.group(0)
        new_bass_index = (bass_index + semitones) % 12
        return m.group(1) + CHORD_NAMES[new_bass_index]

    return transposed_base + _BASS_REGEX.sub(_bass_sub, modifiers)


def is_chord_line(line):
    trimmed = line.strip()
    if not trimmed:
        return False
    if re.search(r'//chords$', trimmed, re.IGNORECASE):
        return True
    if re.search(r'//lyrics$', trimmed, re.IGNORECASE):
        return False
    cleaned = re.sub(r'[xX][0-9]+', '', trimmed)
    cleaned = re.sub(r'[0-9]+[xX]', '', cleaned)
    cleaned = re.sub(r'[()\-|]', ' ', cleaned)
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return False
    return all(CHORD_TOKEN_REGEX.match(tok) for tok in tokens)


def _split_preserving_spaces(rest):
    """Espelha JS `rest.split(/(\\s+)/)` — mantém os separadores de
    espaço como itens próprios da lista, pra preservar o alinhamento
    exato da cifra em cima da sílaba certa da letra."""
    return re.split(r'(\s+)', rest)


def transpose_line(line, semitones):
    leading = re.match(r'^\s*', line).group(0)
    rest = line[len(leading):]
    parts = _split_preserving_spaces(rest)
    transposed = [p if (p == '' or p.isspace()) else transpose_chord(p, semitones) for p in parts]
    return leading + ''.join(transposed)


def transpose_block_content(content, semitones):
    if not semitones:
        return content
    lines = content.split('\n')
    return '\n'.join(
        line if not is_chord_line(line) else transpose_line(line, semitones)
        for line in lines
    )


def highlight_chord_tokens_html(line):
    """Envolve cada token da linha em <span class="chord">, escapando
    HTML (diferente do .js, que não escapa por já saber que o texto vem
    de dentro de um <pre> mostrado como innerHTML — aqui o texto vem
    direto do banco, então precisa escapar pra não virar injeção)."""
    leading = re.match(r'^\s*', line).group(0)
    rest = line[len(leading):]
    parts = _split_preserving_spaces(rest)
    out = []
    for part in parts:
        if part == '' or part.isspace():
            out.append(part)
        else:
            out.append(f'<span class="chord">{html.escape(part)}</span>')
    return leading + ''.join(out)


def split_bracket_subsections(text):
    """Divide o texto de uma seção em sub-blocos, cada um opcionalmente
    precedido por uma linha marcadora "[Nome]" (ex.: uma seção "Refrão"
    cujo corpo tem "[Bis]" no meio) — mesma lógica do loop Jinja em
    view_song.html (linhas ~980-1018): colapsa linhas em branco extras
    dentro de um mesmo bloco (no máximo uma linha vazia entre trechos),
    e um marcador sempre fecha o bloco anterior e abre um novo com esse
    título. Devolve uma lista de {'heading': str|None, 'text': str}."""
    lines = text.split('\n')
    blocks = []
    current_lines = []
    current_heading = None
    last_was_empty = False

    def flush():
        clean = []
        for line in current_lines:
            if line.strip() or (clean and clean[-1].strip()):
                clean.append(line)
        if clean:
            blocks.append({'heading': current_heading, 'text': '\n'.join(clean)})

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']') and len(stripped) > 1:
            flush()
            current_lines = []
            current_heading = stripped[1:-1]
            last_was_empty = False
        else:
            if stripped:
                current_lines.append(line)
                last_was_empty = False
            elif current_lines and not last_was_empty:
                current_lines.append('')
                last_was_empty = True
    flush()
    return blocks


def render_cifra_html(content, semitones=0):
    """Pega o texto puro de uma seção (letra+cifra intercalada) e
    devolve HTML pronto pra ir dentro de um <pre> — mesma lógica de
    renderChords() em view_song.html: transpõe se necessário, realça
    linha de cifra inteira, linha de comentário ("//"), e acorde isolado
    entre barras de compasso fora de linha de cifra."""
    content = transpose_block_content(content, semitones)
    lines = content.split('\n')
    processed = []
    for line in lines:
        plain = line
        if plain.strip().startswith('//'):
            processed.append(f'<span class="comment-line">{html.escape(line)}</span>')
            continue
        if is_chord_line(plain):
            processed.append(highlight_chord_tokens_html(line))
            continue
        escaped = html.escape(line)
        escaped = _BARLINE_CHORD_REGEX.sub(
            lambda m: f'<span class="chord">|</span> <span class="chord">{html.escape(m.group(1))}</span> <span class="chord">|</span>',
            escaped,
        )
        processed.append(escaped)
    return '\n'.join(processed)
