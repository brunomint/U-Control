"""Galeria de imagens: pastas, upload (com conversão de PDF/PPTX pra
imagens), listagem e exclusão. IMAGE_FOLDER e get_current_image_path()
são usadas também por /img (main.py, tela de exibição pública — parte do
núcleo de display, não desta área), por isso ficam exportadas daqui."""
import os

from flask import Blueprint, jsonify, request
from flask_login import login_required
from werkzeug.utils import safe_join, secure_filename
from PIL import Image
import fitz  # PyMuPDF

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
    IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.gif')
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
    max_size = (1920, 1080)  # Full HD - ótimo para projeção

    for file in files:
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Nome de arquivo vazio'}), 400

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'status': 'error', 'message': 'Nome de arquivo inválido'}), 400

        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in ('.mp4', '.webm', '.mov'):
            file_path = os.path.join(target_dir, filename)
            file.save(file_path)
            saved_files.append(filename)
        elif file_ext == '.pdf':
            # Converter PDF para imagens otimizadas para projeção
            pdf_document = fitz.open(stream=file.read(), filetype="pdf")
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]

                # Renderiza em 2x para boa qualidade inicial
                matrix = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=matrix)

                # Converte para PIL para redimensionar e comprimir
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail(max_size, Image.LANCZOS)

                # Salva como JPEG otimizado (muito mais leve que PNG)
                img_path = os.path.join(target_dir, f"{os.path.splitext(filename)[0]}_page-{str(page_num + 1).zfill(4)}.jpg")
                img.save(img_path, 'JPEG', quality=85, optimize=True)
                saved_files.append(os.path.basename(img_path))
        elif file_ext == '.pptx':
            import subprocess, tempfile
            with tempfile.TemporaryDirectory() as tmp:
                pptx_path = os.path.join(tmp, filename)
                file.save(pptx_path)
                subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, pptx_path],
                    capture_output=True, timeout=120
                )
                pdf_path = os.path.splitext(pptx_path)[0] + '.pdf'
                if not os.path.exists(pdf_path):
                    continue
                pdf_document = fitz.open(pdf_path)
                base_name = os.path.splitext(filename)[0]
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    matrix = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=matrix)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.thumbnail(max_size, Image.LANCZOS)
                    img_path = os.path.join(target_dir, f"{base_name}_slide-{str(page_num + 1).zfill(4)}.jpg")
                    img.save(img_path, 'JPEG', quality=85, optimize=True)
                    saved_files.append(os.path.basename(img_path))
        else:
            # Salvar e redimensionar imagens com compressão otimizada
            file_path = os.path.join(target_dir, filename)
            with Image.open(file) as img:
                # Converte para RGB se for RGBA (PNG com transparência)
                if img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (0, 0, 0))  # Fundo preto
                    background.paste(img, mask=img.split()[3])  # Alpha channel
                    img = background

                # Redimensiona mantendo proporção
                img.thumbnail(max_size, Image.LANCZOS)

                # Salva com compressão otimizada
                if file_ext in ['.jpg', '.jpeg']:
                    img.save(file_path, 'JPEG', quality=85, optimize=True)
                elif file_ext == '.png':
                    img.save(file_path, 'PNG', optimize=True, compress_level=6)
                else:
                    img.save(file_path, quality=85, optimize=True)

            saved_files.append(filename)

    return jsonify({'status': 'success', 'saved_files': saved_files}), 200

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
