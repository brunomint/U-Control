"""Galeria de imagens: pastas, upload (com conversão de PDF/PPTX pra
imagens), listagem e exclusão. IMAGE_FOLDER e get_current_image_path()
são usadas também por /img (main.py, tela de exibição pública — parte do
núcleo de display, não desta área), por isso ficam exportadas daqui."""
import logging
import os
import shutil
import subprocess
import posixpath
import tempfile
import threading
import xml.etree.ElementTree as ET
import zipfile

from flask import Blueprint, jsonify, request
from flask_login import login_required
from werkzeug.utils import safe_join, secure_filename
from PIL import Image, ImageOps, UnidentifiedImageError
import fitz  # PyMuPDF

try:  # fotos de iPhone (.heic) — sem o pacote, viram erro claro em vez de 500
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

from extensions import csrf

gallery_bp = Blueprint('gallery', __name__)

# Diretório onde as imagens estão armazenadas
IMAGE_FOLDER = 'static/imagens'


def _safe_folder_path(*parts):
    """Junta IMAGE_FOLDER com os segmentos dados, recusando qualquer
    tentativa de sair da pasta (ex: folder/name/filename contendo '..').
    Retorna None se o caminho resultante escaparia de IMAGE_FOLDER."""
    return safe_join(IMAGE_FOLDER, *parts)


def get_current_image_path():
    images = os.listdir(IMAGE_FOLDER)
    if images:
        return f"/static/imagens/{images[0]}"
    return ""


@gallery_bp.route('/api/image_folders')
def list_image_folders():
    base = IMAGE_FOLDER
    folders = ['Geral']  # pasta raiz sempre existe
    if os.path.exists(base):
        for name in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, name)):
                folders.append(name)
    return jsonify(folders)

# Rota para criar pasta
@gallery_bp.route('/api/image_folders', methods=['POST'])
@login_required
def create_image_folder():
    name = (request.json.get('name') or '').strip()
    if not name or name == 'Geral' or '/' in name or '\\' in name or '..' in name:
        return jsonify({'status': 'error', 'message': 'Nome inválido.'}), 400
    folder_path = os.path.join(IMAGE_FOLDER, name)
    if os.path.exists(folder_path):
        return jsonify({'status': 'error', 'message': 'Pasta já existe.'}), 400
    os.mkdir(folder_path)
    return jsonify({'status': 'success', 'name': name})

# Rota para deletar pasta
@gallery_bp.route('/api/image_folders/<name>', methods=['DELETE'])
@login_required
def delete_image_folder(name):
    if name == 'Geral':
        return jsonify({'status': 'error', 'message': 'Não é possível excluir a pasta Geral.'}), 400
    folder_path = _safe_folder_path(name)
    if folder_path is None:
        return jsonify({'status': 'error', 'message': 'Nome inválido.'}), 400
    if not os.path.exists(folder_path):
        return jsonify({'status': 'error', 'message': 'Pasta não encontrada.'}), 404
    import shutil
    shutil.rmtree(folder_path)
    return jsonify({'status': 'success'})

# Rota para listar as imagens (suporta ?folder=nome)
@gallery_bp.route('/imagens')
def list_images():
    folder = request.args.get('folder', 'Geral')
    if folder == 'Geral':
        target = IMAGE_FOLDER
        prefix = '/static/imagens'
    else:
        target = _safe_folder_path(folder)
        prefix = f'/static/imagens/{folder}'
    if not target or not os.path.exists(target):
        return jsonify([])
    images = [f for f in os.listdir(target) if f.endswith(('.png', '.jpg', '.jpeg', '.gif')) and os.path.isfile(os.path.join(target, f))]
    image_urls = [f'{prefix}/{image}' for image in images]
    return jsonify(image_urls)

@gallery_bp.route('/foto-atual')
def foto_atual():
    return jsonify({'foto_atual': get_current_image_path()})

@gallery_bp.route('/lista-fotos')
def lista_fotos():
    folder = request.args.get('folder', 'Geral')
    if folder == 'Geral':
        target = IMAGE_FOLDER
        prefix = '/static/imagens'
    else:
        target = _safe_folder_path(folder)
        prefix = f'/static/imagens/{folder}'
    if not target or not os.path.exists(target):
        return jsonify({'fotos': []})
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
    VIDEO_EXTS = ('.mp4', '.webm', '.mov')
    items = []
    for f in os.listdir(target):
        if not os.path.isfile(os.path.join(target, f)):
            continue
        lower = f.lower()
        if lower.endswith(IMAGE_EXTS):
            items.append({'url': f'{prefix}/{f}', 'type': 'image'})
        elif lower.endswith(VIDEO_EXTS):
            items.append({'url': f'{prefix}/{f}', 'type': 'video'})
    return jsonify({'fotos': items})


PRESENTATION_EXTS = ('.pptx', '.ppt', '.odp')
# Uma conversão por vez: o Pi tem ~900 MB e duas instâncias do LibreOffice
# com o mesmo perfil brigam (a segunda sai sem converter nada).
_lo_lock = threading.Lock()


def _find_libreoffice():
    """O serviço roda com PATH só do venv (ucontrol-gunicorn), então o
    'libreoffice' do subprocess não era achado — procura nos lugares de
    sempre também."""
    for name in ('libreoffice', 'soffice'):
        found = shutil.which(name)
        if found:
            return found
    for path in ('/usr/bin/libreoffice', '/usr/bin/soffice', '/usr/local/bin/libreoffice',
                 '/Applications/LibreOffice.app/Contents/MacOS/soffice'):
        if os.path.exists(path):
            return path
    return None


def _save_pdf_pages(pdf_document, target_dir, base_name, label, max_size):
    saved = []
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        # Renderiza em 2x para boa qualidade inicial
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.thumbnail(max_size, Image.LANCZOS)
        # JPEG otimizado (muito mais leve que PNG)
        img_path = os.path.join(target_dir, f"{base_name}_{label}-{str(page_num + 1).zfill(4)}.jpg")
        img.save(img_path, 'JPEG', quality=85, optimize=True)
        saved.append(os.path.basename(img_path))
    return saved


_NS_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
_NS_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_NS_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
VIDEO_DIRECT = ('.mp4', '.m4v', '.mov', '.webm')          # o navegador do telão já toca
VIDEO_CONVERT = ('.wmv', '.avi', '.mpg', '.mpeg', '.mkv', '.flv', '.3gp', '.asf')  # ffmpeg -> mp4


def _low_priority():
    """Conversões rodam com prioridade baixa: no Pi o ffmpeg/LibreOffice
    ocupam a CPU inteira e o telão não pode travar se alguém enviar algo
    durante o culto."""
    nice = shutil.which('nice', path='/usr/bin:/bin')
    return [nice, '-n', '19'] if nice else []


def _zip_rels(zf, part):
    """Relações (rId -> (Type, Target absoluto no zip)) de uma parte do pptx."""
    folder, name = posixpath.split(part)
    rels_path = posixpath.join(folder, '_rels', name + '.rels')
    out = {}
    if rels_path not in zf.namelist():
        return out
    for rel in ET.fromstring(zf.read(rels_path)).iter(_NS_REL + 'Relationship'):
        if rel.get('TargetMode') == 'External':
            continue  # vídeo por link (YouTube etc.) não vem no arquivo
        out[rel.get('Id')] = (rel.get('Type', ''), posixpath.normpath(posixpath.join(folder, rel.get('Target', ''))))
    return out


def _pptx_videos_by_slide(pptx_path):
    """[(número do slide na exportação, [vídeos no zip])]. O número é o da
    página no PDF do LibreOffice, que pula os slides ocultos."""
    result = []
    with zipfile.ZipFile(pptx_path) as zf:
        pres = 'ppt/presentation.xml'
        rels = _zip_rels(zf, pres)
        root = ET.fromstring(zf.read(pres))
        page = 0
        for sld in root.iter(_NS_P + 'sldId'):
            target = rels.get(sld.get(_NS_R + 'id'), ('', ''))[1]
            if target not in zf.namelist():
                continue
            if ET.fromstring(zf.read(target)).get('show') == '0':
                continue  # slide oculto: não vira página
            page += 1
            media = []
            for typ, path in _zip_rels(zf, target).values():
                ext = posixpath.splitext(path)[1].lower()
                if (typ.endswith('/video') or typ.endswith('/media')) and ext in VIDEO_DIRECT + VIDEO_CONVERT \
                        and path in zf.namelist() and path not in media:
                    media.append(path)
            if media:
                result.append((page, sorted(media)))
    return result


def _extract_pptx_videos(pptx_path, tmp_dir, target_dir, base_name, env):
    """Põe cada vídeo do PowerPoint na galeria logo depois do slide dele:
    <nome>_slide-0003.jpg, <nome>_slide-0003v1.mp4, <nome>_slide-0004.jpg…"""
    saved = []
    ffmpeg = shutil.which('ffmpeg', path=env.get('PATH'))
    with zipfile.ZipFile(pptx_path) as zf:
        for page, media in _pptx_videos_by_slide(pptx_path):
            for k, path in enumerate(media, 1):
                ext = posixpath.splitext(path)[1].lower()
                final = os.path.join(target_dir, f"{base_name}_slide-{str(page).zfill(4)}v{k}" + ('.mov' if ext == '.mov' else '.webm' if ext == '.webm' else '.mp4'))
                if ext in VIDEO_DIRECT:
                    with zf.open(path) as src, open(final, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                elif ffmpeg:
                    raw = os.path.join(tmp_dir, f'video{page}_{k}{ext}')
                    with zf.open(path) as src, open(raw, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    # escreve num temporário: a galeria não mostra vídeo pela metade
                    part = os.path.join(tmp_dir, f'video{page}_{k}.mp4')
                    proc = subprocess.run(
                        _low_priority() + [ffmpeg, '-y', '-loglevel', 'error', '-threads', '2', '-i', raw, '-vf', "scale='min(1280,iw)':-2",
                         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p',
                         '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', part],
                        capture_output=True, timeout=1800, env=env,
                    )
                    if proc.returncode != 0 or not os.path.exists(part):
                        logging.error("upload: ffmpeg não converteu %s: %s", path, proc.stderr[-300:].decode(errors='replace'))
                        continue
                    shutil.move(part, final)
                else:
                    logging.error("upload: sem ffmpeg pra converter %s", path)
                    continue
                saved.append(os.path.basename(final))
    return saved


def _convert_presentation(src_path, tmp_dir, target_dir, base_name, max_size, soffice):
    """PowerPoint -> PDF (LibreOffice) -> um JPEG por slide. Roda fora da
    requisição: no Pi o LibreOffice leva ~50 s só pra abrir, e o Cloudflare
    desiste da resposta em 100 s."""
    try:
        with _lo_lock:
            profile = os.path.join(tempfile.gettempdir(), 'ucontrol-libreoffice')
            # /usr/bin/libreoffice é um script de shell: precisa de dirname,
            # basename etc. no PATH (o do serviço só tem o venv)
            env = dict(os.environ)
            env['PATH'] = os.pathsep.join(filter(None, [env.get('PATH'), '/usr/local/bin', '/usr/bin', '/bin']))
            proc = subprocess.run(
                _low_priority() + [soffice, f'-env:UserInstallation=file://{profile}', '--headless',
                 '--convert-to', 'pdf', '--outdir', tmp_dir, src_path],
                capture_output=True, timeout=600, env=env,
            )
        pdf_path = os.path.splitext(src_path)[0] + '.pdf'
        if not os.path.exists(pdf_path):
            logging.error("upload: LibreOffice não converteu %s (saída %s): %s", src_path,
                          proc.returncode, (proc.stderr or proc.stdout or b'')[-500:].decode(errors='replace'))
            return
        with fitz.open(pdf_path) as pdf_document:
            saved = _save_pdf_pages(pdf_document, target_dir, base_name, 'slide', max_size)
        logging.info("upload: %s convertido em %d slide(s)", base_name, len(saved))
        if src_path.lower().endswith('.pptx'):
            try:
                videos = _extract_pptx_videos(src_path, tmp_dir, target_dir, base_name, env)
                if videos:
                    logging.info("upload: %s — vídeo(s) dos slides: %s", base_name, ', '.join(videos))
            except Exception:
                logging.exception("upload: falha tirando os vídeos de %s", src_path)
    except Exception:
        logging.exception("upload: falha convertendo %s", src_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@gallery_bp.route('/upload', methods=['POST'])
@csrf.exempt
def upload_files():
    # Sem @login_required de propósito: /presenter é acessado sem login (via
    # QR code, pra qualquer pessoa da igreja enviar fotos durante o culto) e
    # chama esta rota diretamente. A proteção aqui é a validação de caminho
    # abaixo (_safe_folder_path + secure_filename), não autenticação. Também
    # isenta de CSRF: exigir token quebraria o caso de alguém abrir o link
    # direto num celular sem ter carregado a página com o meta tag antes.
    if 'images' not in request.files:
        return jsonify({'status': 'error', 'message': 'Nenhum arquivo enviado'}), 400

    folder = request.form.get('folder', 'Geral')
    if folder == 'Geral':
        target_dir = IMAGE_FOLDER
    else:
        target_dir = _safe_folder_path(folder)
        if target_dir is None:
            return jsonify({'status': 'error', 'message': 'Pasta inválida.'}), 400
        os.makedirs(target_dir, exist_ok=True)

    files = request.files.getlist('images')
    saved_files = []
    converting = []   # apresentações convertendo em segundo plano
    videos_expected = {}  # pptx -> quantos vídeos vão sair dos slides
    errors = []
    max_size = (1920, 1080)  # Full HD - ótimo para projeção

    for file in files:
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Nome de arquivo vazio'}), 400

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'status': 'error', 'message': 'Nome de arquivo inválido'}), 400

        base_name, file_ext = os.path.splitext(filename)
        file_ext = file_ext.lower()
        if file_ext in ('.mp4', '.webm', '.mov'):
            file_path = os.path.join(target_dir, filename)
            file.save(file_path)
            saved_files.append(filename)
        elif file_ext == '.pdf':
            # Converter PDF para imagens otimizadas para projeção
            try:
                with fitz.open(stream=file.read(), filetype="pdf") as pdf_document:
                    saved_files += _save_pdf_pages(pdf_document, target_dir, base_name, 'page', max_size)
            except Exception:
                logging.exception("upload: PDF ilegível %s", filename)
                errors.append(f'{file.filename}: PDF não pôde ser lido.')
        elif file_ext in PRESENTATION_EXTS:
            soffice = _find_libreoffice()
            if not soffice:
                errors.append(f'{file.filename}: o servidor não tem o LibreOffice pra converter apresentações. Salve como PDF e envie o PDF.')
                continue
            tmp_dir = tempfile.mkdtemp(prefix='ucontrol-ppt-')
            src_path = os.path.join(tmp_dir, filename)
            file.save(src_path)
            threading.Thread(
                target=_convert_presentation,
                args=(src_path, tmp_dir, target_dir, base_name, max_size, soffice),
                daemon=True,
            ).start()
            converting.append(filename)
            if file_ext == '.pptx':
                try:  # só lê o índice do zip — rápido
                    n = sum(len(m) for _, m in _pptx_videos_by_slide(src_path))
                    if n:
                        videos_expected[filename] = n
                except Exception:
                    logging.exception("upload: não deu pra ler os vídeos de %s", filename)
        else:
            # Foto: gira conforme o celular gravou (EXIF), reduz pra Full HD
            # e comprime. HEIC (iPhone) e outros formatos sem PNG/JPEG viram JPEG.
            try:
                with Image.open(file) as original:
                    img = ImageOps.exif_transpose(original)
                    # Transparência vira fundo preto (como o telão)
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        img = img.convert('RGBA')
                        background = Image.new('RGB', img.size, (0, 0, 0))
                        background.paste(img, mask=img.split()[3])
                        img = background
                    elif img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')

                    img.thumbnail(max_size, Image.LANCZOS)

                    if file_ext not in ('.jpg', '.jpeg', '.png', '.gif'):
                        file_ext = '.jpg'
                        filename = base_name + file_ext
                    file_path = os.path.join(target_dir, filename)
                    if file_ext in ('.jpg', '.jpeg'):
                        img.save(file_path, 'JPEG', quality=85, optimize=True)
                    elif file_ext == '.png':
                        img.save(file_path, 'PNG', optimize=True, compress_level=6)
                    else:
                        img.save(file_path, quality=85, optimize=True)
                saved_files.append(filename)
            except (UnidentifiedImageError, OSError):
                logging.exception("upload: imagem ilegível %s", filename)
                errors.append(f'{file.filename}: formato não reconhecido. Envie foto (JPG, PNG, HEIC), vídeo, PDF ou PowerPoint.')

    if errors and not saved_files and not converting:
        return jsonify({'status': 'error', 'message': ' '.join(errors), 'errors': errors}), 400
    return jsonify({'status': 'success', 'saved_files': saved_files,
                    'converting': converting, 'videos': videos_expected, 'errors': errors}), 200

# Rota para deletar imagens (suporta ?folder=nome)
@gallery_bp.route('/delete_image', methods=['POST'])
@login_required
def delete_image():
    image_name = request.json.get('image_name')
    folder = request.json.get('folder', 'Geral')
    if not image_name:
        return jsonify({'status': 'error', 'message': 'Nome de imagem não fornecido.'}), 400

    image_path = _safe_folder_path(folder, image_name) if folder != 'Geral' else _safe_folder_path(image_name)
    if image_path is None:
        return jsonify({'status': 'error', 'message': 'Caminho inválido.'}), 400
    if os.path.exists(image_path):
        os.remove(image_path)
        return jsonify({'status': 'success', 'message': 'Imagem deletada com sucesso.'})
    else:
        return jsonify({'status': 'error', 'message': 'Imagem não encontrada.'})

# Rota para deletar múltiplas imagens (suporta folder)
@gallery_bp.route('/delete_images', methods=['POST'])
@login_required
def delete_images():
    image_names = request.json.get('image_names', [])
    folder = request.json.get('folder', 'Geral')
    if not image_names:
        return jsonify({'status': 'error', 'message': 'Nenhuma imagem selecionada.'}), 400

    target_dir = IMAGE_FOLDER if folder == 'Geral' else _safe_folder_path(folder)
    deleted = []
    errors = []
    for name in image_names:
        image_path = safe_join(target_dir, name) if target_dir else None
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            deleted.append(name)
        else:
            errors.append(name)

    return jsonify({'status': 'success', 'deleted': deleted, 'errors': errors})
