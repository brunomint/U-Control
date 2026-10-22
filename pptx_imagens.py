"""Imagens do PowerPoint na versão animada (SVG) do LibreOffice.

A exportação SVG grava cada imagem como PNG e perde duas coisas que o PDF
(e as imagens da galeria) mantêm:

- GIF animado vira o primeiro quadro, parado. Modelos "animados" do Canva
  não usam animação do PowerPoint: o movimento é um GIF (fundo que se mexe,
  enfeites girando);
- a transparência da imagem (<a:alphaModFix amt="20000"/>, "20% visível"):
  o Canva põe um GIF branco a 20% sobre o roxo, e sem isso ele aparece
  branco e opaco;
- o giro de GIF: imagem comum girada sai já girada, mas o GIF sai reto e
  esticado na caixa do giro (uma faixa distorcida no slide).

Aqui cada PNG do SVG é comparado com as imagens do .pptx (mesmo tamanho e
mesmos pixels); achando, volta a ser o GIF e/ou ganha a opacidade."""
import base64
import io
import logging
import math
import posixpath
import re
import zipfile

from PIL import Image, ImageChops, ImageStat

_RE_SLIDE = re.compile(r'ppt/slides/slide\d+\.xml$')
_RE_IMAGE = re.compile(r'<image\b([^>]*?)xlink:href="data:image/png;base64,([A-Za-z0-9+/=\s]+)"')
_RE_BLIP = re.compile(r'<a:blip\b[^>]*\br:embed="([^"]+)"[^>]*?(?:/>|>(.*?)</a:blip>)', re.S)
_PARECIDO = 2.0  # diferença média (0-255) até onde o PNG é a mesma imagem
_EXTS = ('.png', '.gif', '.jpg', '.jpeg')


def _slides_visiveis(zf):
    for nome in zf.namelist():
        if _RE_SLIDE.match(nome) and 'show="0"' not in zf.read(nome)[:2000].decode('utf-8', 'replace'):
            yield nome


def _rels(zf, slide):
    caminho = posixpath.join(posixpath.dirname(slide), '_rels', posixpath.basename(slide) + '.rels')
    if caminho not in zf.namelist():
        return {}
    xml = zf.read(caminho).decode('utf-8', 'replace')
    return {rid: posixpath.normpath(posixpath.join(posixpath.dirname(slide), alvo))
            for rid, alvo in re.findall(r'Id="([^"]+)"[^>]*?Target="([^"]+)"', xml)}


def _animado(dados):
    try:
        with Image.open(io.BytesIO(dados)) as im:
            return getattr(im, 'n_frames', 1) > 1
    except Exception:
        return False


_RE_PIC = re.compile(r'<p:pic>.*?</p:pic>', re.S)
_EMU_POR_UNIDADE = 360  # SVG do LibreOffice em 1/100 mm; 1 mm = 36000 EMU


def _gifs_girados(zf, slide, rels, gifs):
    """GIFs girados/espelhados do slide: [(caixa que o LibreOffice grava,
    (x, y, largura, altura) sem girar, transform)]."""
    lugares = []
    for pic in _RE_PIC.findall(zf.read(slide).decode('utf-8', 'replace')):
        m = re.search(r'<a:blip\b[^>]*\br:embed="([^"]+)"', pic)
        x = re.search(r'<a:xfrm\b([^>]*)>\s*<a:off x="(-?\d+)" y="(-?\d+)"/>\s*<a:ext cx="(\d+)" cy="(\d+)"/>', pic)
        if not m or not x or rels.get(m.group(1)) not in gifs:
            continue
        attrs = x.group(1)
        rot = re.search(r'rot="(-?\d+)"', attrs)
        graus = int(rot.group(1)) / 60000 if rot else 0.0
        flip_h, flip_v = 'flipH="1"' in attrs or 'flipH="true"' in attrs, 'flipV="1"' in attrs or 'flipV="true"' in attrs
        if not graus % 360 and not flip_h and not flip_v:
            continue
        ox, oy, w, h = (int(v) / _EMU_POR_UNIDADE for v in x.groups()[1:])
        cx, cy = ox + w / 2, oy + h / 2
        c, s_ = abs(math.cos(math.radians(graus))), abs(math.sin(math.radians(graus)))
        bw, bh = w * c + h * s_, w * s_ + h * c
        transform = f'rotate({graus:.3f} {cx:.1f} {cy:.1f})'
        if flip_h or flip_v:
            transform += f' translate({cx:.1f} {cy:.1f}) scale({-1 if flip_h else 1} {-1 if flip_v else 1}) translate({-cx:.1f} {-cy:.1f})'
        lugares.append(((cx - bw / 2, cy - bh / 2, bw, bh), (ox, oy, w, h), transform))
    return lugares


def tem_gif_animado(pptx_path):
    """Algum slide visível usa um GIF animado?"""
    with zipfile.ZipFile(pptx_path) as zf:
        for slide in _slides_visiveis(zf):
            for alvo in _rels(zf, slide).values():
                if alvo.lower().endswith('.gif') and alvo in zf.namelist() and _animado(zf.read(alvo)):
                    return True
    return False


def _cinza(im):
    im = im.convert('RGBA')
    fundo = Image.new('RGBA', im.size, (0, 0, 0, 255))
    fundo.alpha_composite(im)
    return fundo.convert('L').resize((64, 64))


def _catalogo(pptx_path):
    """Imagens usadas nos slides: tamanho -> [{cinza, gif (data URI ou None),
    opacidades usadas}]."""
    usos = {}  # caminho no zip -> set de opacidades (1.0 = sem alphaModFix)
    girados = []
    with zipfile.ZipFile(pptx_path) as zf:
        gifs = {n for n in zf.namelist() if n.lower().endswith('.gif') and _animado(zf.read(n))}
        for slide in _slides_visiveis(zf):
            rels = _rels(zf, slide)
            girados += _gifs_girados(zf, slide, rels, gifs)
            for rid, efeitos in _RE_BLIP.findall(zf.read(slide).decode('utf-8', 'replace')):
                alvo = rels.get(rid)
                if not alvo or not alvo.lower().endswith(_EXTS) or alvo not in zf.namelist():
                    continue
                m = re.search(r'<a:alphaModFix amt="(\d+)"', efeitos or '')
                usos.setdefault(alvo, set()).add(int(m.group(1)) / 100000 if m else 1.0)
        catalogo = {}
        for alvo, opacidades in usos.items():
            dados = zf.read(alvo)
            try:
                with Image.open(io.BytesIO(dados)) as im:
                    im.seek(0)
                    gif = alvo.lower().endswith('.gif') and getattr(im, 'n_frames', 1) > 1
                    catalogo.setdefault(im.size, []).append({
                        'cinza': _cinza(im),
                        'gif': 'data:image/gif;base64,' + base64.b64encode(dados).decode('ascii') if gif else None,
                        # a mesma imagem com transparências diferentes: não dá pra saber qual é qual
                        'opacidade': next(iter(opacidades)) if len(opacidades) == 1 else 1.0,
                    })
            except Exception:
                continue
    return catalogo, girados


def _girar(attrs, girados):
    """Caixa do GIF no SVG = caixa de um GIF girado do .pptx: volta a ser a
    imagem reta, com o giro como transform."""
    try:
        caixa = [float(re.search(r'\b%s="(-?[\d.]+)"' % k, attrs).group(1)) for k in ('x', 'y', 'width', 'height')]
    except AttributeError:
        return attrs
    for bbox, (x, y, w, h), transform in girados:
        tolerancia = max(bbox[2], bbox[3]) * 0.01 + 20
        if all(abs(a - b) <= tolerancia for a, b in zip(caixa, bbox)):
            for k, v in (('x', x), ('y', y), ('width', w), ('height', h)):
                attrs = re.sub(r'\b%s="-?[\d.]+"' % k, f'{k}="{v:.0f}"', attrs, count=1)
            return attrs + f'transform="{transform}" '
    return attrs


def corrigir_svg(svg_path, pptx_path):
    """Devolve ao SVG os GIFs animados e a transparência das imagens.
    Retorna (GIFs devolvidos, imagens com transparência)."""
    catalogo, girados = _catalogo(pptx_path)
    precisa = any(c['gif'] or c['opacidade'] < 1 for lista in catalogo.values() for c in lista)
    if not precisa:
        return 0, 0
    contagem = {'gif': 0, 'opacidade': 0, 'giro': 0}

    def trocar(m):
        attrs, b64 = m.group(1), m.group(2)
        try:
            with Image.open(io.BytesIO(base64.b64decode(b64))) as png:
                opcoes = catalogo.get(png.size)
                if not opcoes:
                    return m.group(0)
                quadro = _cinza(png)
        except Exception:
            return m.group(0)
        for c in opcoes:
            if ImageStat.Stat(ImageChops.difference(c['cinza'], quadro)).mean[0] > _PARECIDO:
                continue
            href = 'data:image/png;base64,' + b64
            if c['gif']:
                href = c['gif']
                contagem['gif'] += 1
                girado = _girar(attrs, girados)
                if girado != attrs:
                    attrs = girado
                    contagem['giro'] += 1
            if c['opacidade'] < 1 and 'opacity=' not in attrs:
                attrs += f'opacity="{c["opacidade"]:.3f}" '
                contagem['opacidade'] += 1
            return f'<image{attrs}xlink:href="{href}"'
        return m.group(0)

    with open(svg_path, encoding='utf-8') as f:
        svg = f.read()
    novo = _RE_IMAGE.sub(trocar, svg)
    if contagem['gif'] or contagem['opacidade']:
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(novo)
        logging.info("upload: versão animada — %d GIF(s) animado(s) (%d girado(s)), %d imagem(ns) com transparência",
                     contagem['gif'], contagem['giro'], contagem['opacidade'])
    return contagem['gif'], contagem['opacidade']
