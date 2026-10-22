"""Fontes embutidas no PowerPoint (o Canva sempre embute; o PowerPoint, com
"Inserir fontes no arquivo") entregues ao LibreOffice na conversão.

Sem isso o LibreOffice troca a fonte que não tem no computador por outra
(em geral mais larga) e o texto dos slides quebra e sai do lugar — ex.:
Bebas Neue, estreita, virava DejaVu Sans e "Características" partia no
meio.

No .pptx elas ficam em ppt/fonts/*.fntdata, no formato EOT (Embedded
OpenType): um cabeçalho e a fonte TrueType inteira em seguida. Extraídas,
vão pra pasta de fontes do perfil do LibreOffice (<perfil>/user/fonts),
que ele lê ao abrir. O nome da família é trocado pelo que o PowerPoint usa
(typeface="Prompt Light"), porque dentro do arquivo ela pode se chamar
"Prompt" com estilo "Light", e aí o LibreOffice não acha.

Na versão animada (SVG) o texto é desenhado pelo navegador da tela, que
também precisa da fonte: embutir_no_svg() põe as mesmas fontes como
@font-face (o LibreOffice embute "SVG fonts", que o Chrome não lê)."""
import base64
import io
import logging
import os
import posixpath
import re
import shutil
import struct
import xml.etree.ElementTree as ET
import zipfile

_NS_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
_NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_NS_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
# papel no <p:embeddedFont> -> (estilo, negrito, itálico)
_PAPEIS = {'regular': ('Regular', False, False), 'bold': ('Bold', True, False),
           'italic': ('Italic', False, True), 'boldItalic': ('Bold Italic', True, True)}
_EOT_COMPRIMIDA = 0x4          # TTEMBED_TTCOMPRESSED (MicroType Express): não suportado
_EOT_XOR = 0x10000000          # TTEMBED_XORENCRYPTDATA


def _ttf_do_eot(dados):
    """Fonte TrueType de dentro do .fntdata, ou None se não der."""
    if dados[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
        return dados  # já é TTF/OTF puro
    if len(dados) < 36 or struct.unpack_from('<H', dados, 34)[0] != 0x504C:
        return None
    tamanho, tamanho_fonte, _versao, flags = struct.unpack_from('<IIII', dados, 0)
    if flags & _EOT_COMPRIMIDA or tamanho > len(dados) or tamanho_fonte > tamanho:
        return None
    fonte = dados[tamanho - tamanho_fonte:tamanho]
    if flags & _EOT_XOR:
        fonte = bytes(b ^ 0x50 for b in fonte)
    return fonte


def _renomear(ttf, familia, estilo, negrito, italico):
    try:
        from fontTools.ttLib import TTFont
    except ImportError:  # pragma: no cover — vem com o WeasyPrint
        return ttf
    fonte = TTFont(io.BytesIO(ttf))
    nomes = fonte['name']
    for nid in (16, 17, 21, 22):  # família/estilo "tipográficos" confundem a busca
        nomes.removeNames(nameID=nid)
    postscript = re.sub(r'[^A-Za-z0-9-]', '', f'{familia}-{estilo}')[:63] or 'Fonte'
    for nid, valor in ((1, familia), (2, estilo), (4, f'{familia} {estilo}'), (6, postscript)):
        nomes.setName(valor, nid, 3, 1, 0x409)
        nomes.setName(valor, nid, 1, 0, 0)
    if 'OS/2' in fonte:
        os2 = fonte['OS/2']
        os2.usWeightClass = 700 if negrito else 400
        os2.fsSelection = (os2.fsSelection & ~0b1100001) | (0b100000 if negrito else 0) \
            | (0b1 if italico else 0) | (0 if negrito or italico else 0b1000000)
    saida = io.BytesIO()
    fonte.save(saida)
    return saida.getvalue()


def fontes_embutidas(pptx_path):
    """[(nome do arquivo, bytes TTF)] das fontes embutidas no .pptx."""
    resultado = []
    with zipfile.ZipFile(pptx_path) as zf:
        pres = 'ppt/presentation.xml'
        rels_path = 'ppt/_rels/presentation.xml.rels'
        if rels_path not in zf.namelist():
            return []
        rels = {}
        for rel in ET.fromstring(zf.read(rels_path)).iter(_NS_REL + 'Relationship'):
            if rel.get('Type', '').endswith('/font'):
                rels[rel.get('Id')] = posixpath.normpath(posixpath.join('ppt', rel.get('Target', '')))
        if not rels:
            return []
        for emb in ET.fromstring(zf.read(pres)).iter(_NS_P + 'embeddedFont'):
            fonte = emb.find(_NS_P + 'font')
            familia = (fonte.get('typeface') if fonte is not None else '') or ''
            for papel, (estilo, negrito, italico) in _PAPEIS.items():
                el = emb.find(_NS_P + papel)
                alvo = rels.get(el.get(_NS_R + 'id')) if el is not None else None
                if not familia or not alvo or alvo not in zf.namelist():
                    continue
                ttf = _ttf_do_eot(zf.read(alvo))
                if not ttf:
                    logging.info("upload: fonte embutida %s (%s) em formato não suportado", familia, papel)
                    continue
                try:
                    ttf = _renomear(ttf, familia, estilo, negrito, italico)
                except Exception:
                    logging.exception("upload: não deu pra ajustar o nome da fonte %s", familia)
                nome = re.sub(r'[^A-Za-z0-9_-]', '_', f'{familia}-{papel}') + '.ttf'
                resultado.append((nome, ttf))
    return resultado


def preparar(pptx_path, profile):
    """Deixa em <perfil>/user/fonts só as fontes deste arquivo (a pasta é a
    mesma em todas as conversões; o LibreOffice relê ao abrir)."""
    pasta = os.path.join(profile, 'user', 'fonts')
    shutil.rmtree(pasta, ignore_errors=True)
    if not pptx_path.lower().endswith('.pptx'):
        return []
    try:
        fontes = fontes_embutidas(pptx_path)
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return []
    if fontes:
        os.makedirs(pasta, exist_ok=True)
        for nome, ttf in fontes:
            with open(os.path.join(pasta, nome), 'wb') as f:
                f.write(ttf)
        logging.info("upload: fontes embutidas usadas: %s", ', '.join(n for n, _ in fontes))
    return [n for n, _ in fontes]


def embutir_no_svg(svg_path, pptx_path):
    """@font-face com as fontes embutidas do .pptx no começo do SVG."""
    try:
        fontes = fontes_embutidas(pptx_path) if pptx_path.lower().endswith('.pptx') else []
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return 0
    if not fontes:
        return 0
    regras = []
    for nome, ttf in fontes:
        papel = nome.rsplit('-', 1)[1][:-4]
        _estilo, negrito, italico = _PAPEIS[papel]
        familia = _familia(ttf) or nome
        regras.append('@font-face{font-family:"%s";font-weight:%s;font-style:%s;src:url(data:font/ttf;base64,%s)}' % (
            familia.replace('"', ''), 'bold' if negrito else 'normal', 'italic' if italico else 'normal',
            base64.b64encode(ttf).decode('ascii')))
    with open(svg_path, encoding='utf-8') as f:
        svg = f.read()
    m = re.search(r'<svg\b[^>]*>', svg)
    if not m:
        return 0
    estilo = '<style type="text/css"><![CDATA[%s]]></style>' % ''.join(regras)
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(svg[:m.end()] + estilo + svg[m.end():])
    return len(regras)


def _familia(ttf):
    try:
        from fontTools.ttLib import TTFont
        return TTFont(io.BytesIO(ttf))['name'].getDebugName(1)
    except Exception:
        return None
