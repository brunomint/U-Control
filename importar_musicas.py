"""Lê músicas de outros programas e devolve no formato do U-Control:
{'title', 'author', 'sections': [{'title', 'text': [texto]}], 'origem'}.

A cifra fica no estilo do U-Control (e do Cifra Club): linha de acordes em
cima da linha da letra. Formatos:

- Holyrics: exportação JSON (uma música ou uma lista; "slides" desde a
  v2.21, "lyrics.paragraphs" nas antigas) e TXT (título = nome do arquivo,
  um slide por parágrafo);
- OpenLyrics (.xml): o formato aberto do OpenLP e de outros, com
  <chord name="G"/> (0.8) ou <chord root="G" .../> (0.9) no meio da letra;
- ChordPro (.cho, .chordpro, .chopro, .crd, .pro): [G] no meio da letra e
  {title:}, {artist:}, {start_of_chorus} ...;
- texto simples (.txt): parágrafos separados por linha em branco; um
  cabeçalho como "[Refrão]" ou "Ponte:" vira o título da seção;
- .zip com qualquer um desses dentro.

Só lê: gravar no banco é com blueprints/importar.py."""
import io
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile

LIMITE_ARQUIVOS = 3000  # dentro de um .zip
EXT_CHORDPRO = ('.cho', '.chordpro', '.chopro', '.crd', '.pro')
EXT_ACEITAS = ('.json', '.xml', '.txt', '.zip') + EXT_CHORDPRO

_NS_OL = '{http://openlyrics.info/namespace/2009/song}'
# v1 -> Verse 1; c -> Chorus ... (nome das seções do OpenLyrics/OpenLP)
_TIPOS = {'v': 'Verse', 'c': 'Chorus', 'b': 'Bridge', 'p': 'Pre-Chorus', 'i': 'Intro', 'e': 'Final', 'o': ''}
_RE_CABECALHO = re.compile(
    r'^\s*(?:\[([^\]]{1,40})\]|((?:verso|verse|refr[aã]o|coro|chorus|ponte|bridge|pr[eé][- ]?refr[aã]o|pre[- ]?chorus|intro|final|solo|tag|interl[uú]dio)\b[^:\n]{0,20}):?)\s*$',
    re.I)


class ArquivoInvalido(Exception):
    pass


def _musica(titulo, autor, secoes, origem):
    secoes = [{'title': t or '', 'text': [txt.strip('\n')]} for t, txt in secoes if txt and txt.strip()]
    titulo = (titulo or '').strip()
    if not titulo or not secoes:
        return None
    return {'title': titulo[:300], 'author': (autor or '').strip()[:300], 'sections': secoes, 'origem': origem}


# --- acordes no meio da letra -> linha de acordes em cima ----------------

def _linha_com_acordes(linha):
    """'[G]Santo, [D/F#]santo' -> 'G     D/F#\\nSanto, santo'. Sem acorde, a
    linha volta igual."""
    if '[' not in linha:
        return linha
    acordes, letra = [], ''
    pos = 0
    for m in re.finditer(r'\[([^\]\s]{1,12})\]', linha):
        letra += linha[pos:m.start()]
        acordes.append((len(letra), m.group(1)))
        pos = m.end()
    letra += linha[pos:]
    if not acordes:
        return linha
    cifra = ''
    for col, acorde in acordes:
        if len(cifra) > col:
            col = len(cifra) + 1  # acordes colados: um espaço entre eles
        cifra = cifra.ljust(col) + acorde
    letra = letra.rstrip()
    return cifra if not letra.strip() else f'{cifra}\n{letra}'


def _bloco_com_acordes(texto):
    return '\n'.join(_linha_com_acordes(linha) for linha in texto.split('\n'))


# --- Holyrics JSON --------------------------------------------------------

def _holyrics_json(dados, nome):
    itens = dados if isinstance(dados, list) else [dados]
    musicas = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        slides = item.get('slides')
        if not slides and isinstance(item.get('lyrics'), dict):
            slides = item['lyrics'].get('paragraphs')
        secoes = []
        for i, s in enumerate(slides or [], 1):
            if not isinstance(s, dict):
                continue
            texto = s.get('text') or ''
            secoes.append((s.get('slide_description') or s.get('description') or f'Verse {i}', texto))
        m = _musica(item.get('title'), item.get('artist') or item.get('author'), secoes, f'Holyrics ({nome})')
        if m:
            musicas.append(m)
    if not musicas:
        raise ArquivoInvalido(f'{nome}: JSON sem músicas no formato do Holyrics.')
    return musicas


# --- OpenLyrics ----------------------------------------------------------

def _nome_secao(nome):
    m = re.match(r'^([a-z])(\d*)([a-z]?)$', (nome or '').lower())
    if not m:
        return nome or ''
    base = _TIPOS.get(m.group(1), '')
    num = m.group(2)
    return f'{base} {num}'.strip() if base else ''


def _texto_lines(lines):
    """<lines> do OpenLyrics -> texto com [acorde] no lugar dos <chord>."""
    partes = []

    def andar(el):
        tag = el.tag.replace(_NS_OL, '')
        if tag == 'chord':
            nome = el.get('name') or ''.join(filter(None, (el.get('root'), el.get('structure') and _estrutura(el.get('structure')))))
            if el.get('bass'):
                nome += '/' + el.get('bass')
            if nome:
                partes.append(f'[{nome}]')
        elif tag == 'br':
            partes.append('\n')
        elif tag == 'comment':
            return
        if el.text and tag not in ('br', 'comment'):
            partes.append(el.text)
        for filho in el:
            andar(filho)
            if filho.tail:
                partes.append(filho.tail)

    andar(lines)
    return re.sub(r'[ \t]*\n[ \t]*', '\n', ''.join(partes)).strip()


def _estrutura(s):
    # 0.9: structure="min7" etc. — o comum vira a cifra brasileira
    return {'maj': '', 'min': 'm', 'min7': 'm7', 'dom7': '7', 'maj7': '7M', 'sus4': 'sus4', 'dim': 'º', 'aug': '+'}.get(s, s)


def _openlyrics(conteudo, nome):
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        raise ArquivoInvalido(f'{nome}: XML inválido.')
    if raiz.tag.replace(_NS_OL, '') != 'song':
        raise ArquivoInvalido(f'{nome}: não é uma música no formato OpenLyrics.')
    titulo = raiz.findtext(f'{_NS_OL}properties/{_NS_OL}titles/{_NS_OL}title')
    autores = [a.text for a in raiz.iterfind(f'{_NS_OL}properties/{_NS_OL}authors/{_NS_OL}author') if a.text]
    secoes = []
    for verso in raiz.iterfind(f'{_NS_OL}lyrics/{_NS_OL}verse'):
        blocos = [_texto_lines(l) for l in verso.iterfind(f'{_NS_OL}lines')]
        texto = '\n'.join(b for b in blocos if b)
        secoes.append((_nome_secao(verso.get('name')), _bloco_com_acordes(texto)))
    m = _musica(titulo, ', '.join(autores), secoes, f'OpenLyrics ({nome})')
    if not m:
        raise ArquivoInvalido(f'{nome}: música sem título ou sem letra.')
    return [m]


# --- ChordPro ------------------------------------------------------------

_RE_DIRETIVA = re.compile(r'^\s*\{\s*([a-z_]+)\s*(?::\s*(.*?))?\s*\}\s*$', re.I)


def _chordpro(texto, nome):
    titulo, autor = None, None
    secoes, atual, linhas = [], None, []
    n_verso = 0

    def fechar():
        nonlocal linhas, atual
        if any(l.strip() for l in linhas):
            secoes.append((atual, _bloco_com_acordes('\n'.join(linhas).strip('\n'))))
        linhas, atual = [], None

    for linha in texto.splitlines():
        if linha.lstrip().startswith('#'):
            continue
        d = _RE_DIRETIVA.match(linha)
        if d:
            chave, valor = d.group(1).lower(), (d.group(2) or '').strip()
            if chave in ('title', 't'):
                titulo = valor
            elif chave in ('artist', 'subtitle', 'st', 'composer') and not autor:
                autor = valor
            elif chave in ('start_of_chorus', 'soc'):
                fechar(); atual = valor or 'Chorus'
            elif chave in ('start_of_verse', 'sov'):
                fechar(); n_verso += 1; atual = valor or f'Verse {n_verso}'
            elif chave in ('start_of_bridge', 'sob'):
                fechar(); atual = valor or 'Bridge'
            elif chave in ('end_of_chorus', 'eoc', 'end_of_verse', 'eov', 'end_of_bridge', 'eob'):
                fechar()
            elif chave in ('comment', 'c', 'comment_italic', 'ci', 'comment_box', 'cb'):
                fechar(); atual = valor
            continue
        if not linha.strip():
            if atual is None or not any(l.strip() for l in linhas):
                fechar()
            else:
                linhas.append('')
            continue
        if atual is None and not linhas:
            n_verso += 1
            atual = f'Verse {n_verso}'
        linhas.append(linha.rstrip())
    fechar()
    m = _musica(titulo or os.path.splitext(nome)[0], autor, secoes, f'ChordPro ({nome})')
    if not m:
        raise ArquivoInvalido(f'{nome}: ChordPro sem letra.')
    return [m]


# --- texto simples (Holyrics TXT e outros) -------------------------------

def _texto(texto, nome):
    titulo = os.path.splitext(os.path.basename(nome))[0].strip()
    paragrafos = [p.strip('\n') for p in re.split(r'\n\s*\n', texto.replace('\r\n', '\n')) if p.strip()]
    secoes = []
    n_verso = 0
    for p in paragrafos:
        linhas = p.split('\n')
        m = _RE_CABECALHO.match(linhas[0])
        if m and len(linhas) > 1:
            secoes.append(((m.group(1) or m.group(2)).strip(), '\n'.join(linhas[1:])))
        else:
            n_verso += 1
            secoes.append((f'Verse {n_verso}', p))
    m = _musica(titulo, '', secoes, f'Texto ({nome})')
    if not m:
        raise ArquivoInvalido(f'{nome}: arquivo de texto vazio.')
    return [m]


# --- entrada --------------------------------------------------------------

def _decodificar(dados):
    if dados[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return dados.decode('utf-16')  # "Unicode" do Bloco de Notas
    try:
        return dados.decode('utf-8-sig')
    except UnicodeDecodeError:
        return dados.decode('cp1252', errors='replace')  # TXT antigo do Windows


def ler(nome, dados):
    """(nome do arquivo, bytes) -> lista de músicas. Arquivo que não dá pra
    ler levanta ArquivoInvalido com a explicação."""
    ext = os.path.splitext(nome.lower())[1]
    if ext == '.zip':
        return _zip(nome, dados)
    if ext == '.muf':
        raise ArquivoInvalido(f'{nome}: o U-Control ainda não lê o .muf do Holyrics. '
                              'Exporte as músicas do Holyrics em outro formato (JSON ou TXT).')
    if ext not in EXT_ACEITAS:
        raise ArquivoInvalido(f'{nome}: formato não reconhecido.')
    texto = _decodificar(dados)
    if ext == '.json':
        try:
            return _holyrics_json(json.loads(texto), nome)
        except ValueError:
            raise ArquivoInvalido(f'{nome}: JSON inválido.')
    if ext == '.xml':
        return _openlyrics(texto.encode('utf-8'), nome)
    if ext in EXT_CHORDPRO or (ext == '.txt' and re.search(r'^\s*\{\s*(title|t)\s*:', texto, re.M | re.I)):
        return _chordpro(texto, nome)
    return _texto(texto, nome)


def _zip(nome, dados):
    try:
        zf = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ArquivoInvalido(f'{nome}: .zip danificado.')
    musicas, erros = [], []
    with zf:
        internos = [i for i in zf.infolist() if not i.is_dir() and not os.path.basename(i.filename).startswith('.')]
        if len(internos) > LIMITE_ARQUIVOS:
            raise ArquivoInvalido(f'{nome}: arquivos demais dentro do .zip (máximo {LIMITE_ARQUIVOS}).')
        for info in internos:
            interno = os.path.basename(info.filename)
            if os.path.splitext(interno.lower())[1] in ('.zip',):
                continue
            try:
                musicas += ler(interno, zf.read(info))
            except ArquivoInvalido as e:
                erros.append(str(e))
    if not musicas:
        raise ArquivoInvalido(f'{nome}: nenhuma música reconhecida dentro do .zip.' + (f' ({erros[0]})' if erros else ''))
    return musicas
