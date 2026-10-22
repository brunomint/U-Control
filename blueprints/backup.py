"""Backup e restauração: tudo que é da igreja num .zip só, pra guardar ou
levar de uma instalação pra outra (Pi -> Windows, PC novo...). O mesmo
arquivo serve em todas: Windows, Pi e Docker têm o mesmo banco.

O que vai no .zip:
    manifest.json     o que é (app, formato, versão, data, tipo de instalação)
    banco/users.db    músicas e cifras, ordens de culto, usuários, configurações
    imagens/...       fotos, slides e vídeos da galeria
    audio/...         áudios baixados
    bibles/...        Bíblias com direitos autorais que a igreja colocou
                      (paths.BIBLES_PRIVATE_DIR)

Restaurar troca tudo isso pelo que está no arquivo. Antes, guarda o que
havia em <instance>/backups/antes-de-restaurar-*.zip."""
import datetime
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile

from flask import Blueprint, after_this_request, current_app, jsonify, render_template, request, send_file
from flask_login import login_required, logout_user

import paths
import updates
from extensions import db

backup_bp = Blueprint('backup', __name__)

FORMATO = 1
PASTAS = {  # nome no .zip -> pasta no disco
    'imagens': lambda: paths.IMAGE_FOLDER,
    'audio': lambda: paths.AUDIO_DIR,
    'bibles': lambda: paths.BIBLES_PRIVATE_DIR,
}
GUARDAR_ANTES = 3  # cópias automáticas "antes de restaurar" mantidas
# Já comprimidos: guardar sem comprimir de novo (no Pi, poupa minutos de CPU)
_SEM_COMPRIMIR = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mov', '.mp3', '.m4a', '.zip')


class BackupInvalido(Exception):
    pass


def _db_path():
    return db.engine.url.database


def _pasta_backups():
    pasta = os.path.join(current_app.instance_path, 'backups')
    os.makedirs(pasta, exist_ok=True)
    return pasta


def criar_backup(destino):
    """Escreve o .zip em `destino`. A cópia do banco usa a API de backup do
    SQLite: fica consistente mesmo com o U-Control em uso."""
    with tempfile.TemporaryDirectory(prefix='ucontrol-backup-') as tmp:
        copia = os.path.join(tmp, 'users.db')
        src = sqlite3.connect(_db_path())
        dst = sqlite3.connect(copia)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        manifest = {
            'app': 'U-Control', 'formato': FORMATO, 'versao': updates.current_version(),
            'criado': datetime.datetime.now().isoformat(timespec='seconds'),
            'instalacao': updates.install_kind(),
        }
        with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.write(copia, 'banco/users.db')
            for nome, pasta in PASTAS.items():
                pasta = pasta()
                if not os.path.isdir(pasta):
                    continue
                for raiz, _, arquivos in os.walk(pasta):
                    for arq in arquivos:
                        caminho = os.path.join(raiz, arq)
                        rel = os.path.relpath(caminho, pasta).replace(os.sep, '/')
                        tipo = zipfile.ZIP_STORED if arq.lower().endswith(_SEM_COMPRIMIR) else zipfile.ZIP_DEFLATED
                        zf.write(caminho, f'{nome}/{rel}', compress_type=tipo)
    return manifest


def _revisoes_conhecidas():
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option('script_location', paths.MIGRATIONS_DIR)
    return {r.revision for r in ScriptDirectory.from_config(cfg).walk_revisions()}


def _conferir(zf, tmp):
    """Valida o arquivo e extrai o banco. Devolve (manifest, caminho do banco)."""
    try:
        manifest = json.loads(zf.read('manifest.json'))
    except (KeyError, ValueError):
        raise BackupInvalido('Este arquivo não é um backup do U-Control.')
    if manifest.get('app') != 'U-Control' or 'banco/users.db' not in zf.namelist():
        raise BackupInvalido('Este arquivo não é um backup do U-Control.')
    if manifest.get('formato', 0) > FORMATO:
        raise BackupInvalido('Backup de uma versão mais nova do U-Control. Atualize este antes de restaurar.')
    for nome in zf.namelist():
        partes = nome.split('/')
        if nome.startswith('/') or '\\' in nome or '..' in partes or ':' in partes[0] \
                or (partes[0] not in PASTAS and nome not in ('manifest.json', 'banco/users.db')):
            raise BackupInvalido(f'Arquivo estranho dentro do backup: {nome}')

    banco = os.path.join(tmp, 'users.db')
    with zf.open('banco/users.db') as src, open(banco, 'wb') as dst:
        shutil.copyfileobj(src, dst)
    try:
        con = sqlite3.connect(banco)
        try:
            if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise BackupInvalido('O banco dentro do backup está corrompido.')
            revisao = con.execute('SELECT version_num FROM alembic_version').fetchone()
        finally:
            con.close()
    except sqlite3.DatabaseError:
        raise BackupInvalido('O banco dentro do backup não pôde ser lido.')
    if revisao and revisao[0] not in _revisoes_conhecidas():
        raise BackupInvalido('Backup de uma versão mais nova do U-Control. Atualize este antes de restaurar.')
    return manifest, banco


def _trocar_pasta(zf, nome, destino):
    """Extrai <nome>/... ao lado de `destino` e troca as pastas no fim, pra
    nunca ficar pela metade se der erro no meio."""
    destino = os.path.abspath(destino)
    nova, velha = destino + '.restaurando', destino + '.antiga'
    for p in (nova, velha):
        shutil.rmtree(p, ignore_errors=True)
    os.makedirs(nova)
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(nome + '/'):
            continue
        alvo = os.path.join(nova, *info.filename.split('/')[1:])
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        with zf.open(info) as src, open(alvo, 'wb') as dst:
            shutil.copyfileobj(src, dst)
    if os.path.exists(destino):
        os.rename(destino, velha)
    os.rename(nova, destino)
    shutil.rmtree(velha, ignore_errors=True)


def restaurar(arquivo_zip):
    with tempfile.TemporaryDirectory(prefix='ucontrol-restaurar-') as tmp, zipfile.ZipFile(arquivo_zip) as zf:
        manifest, banco = _conferir(zf, tmp)

        # Cópia de segurança do que existe agora
        pasta = _pasta_backups()
        agora = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        criar_backup(os.path.join(pasta, f'antes-de-restaurar-{agora}.zip'))
        antigos = sorted(f for f in os.listdir(pasta) if f.startswith('antes-de-restaurar-'))
        for f in antigos[:-GUARDAR_ANTES]:
            os.remove(os.path.join(pasta, f))

        # Banco: a API de backup do SQLite escreve por cima do arquivo em uso
        # (funciona com o WAL e com as outras conexões abertas)
        db.session.remove()
        src = sqlite3.connect(banco)
        dst = sqlite3.connect(_db_path())
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        db.engine.dispose()

        for nome, pasta_destino in PASTAS.items():
            _trocar_pasta(zf, nome, pasta_destino())

    # Backup de versão mais antiga: atualiza o banco pra esta versão
    import flask_migrate
    flask_migrate.upgrade(directory=paths.MIGRATIONS_DIR)

    # Estado em memória que vem do banco
    from blueprints.countdown import init_countdown_state
    from blueprints.ticker import init_ticker_state
    init_countdown_state()
    init_ticker_state()
    return manifest


def _resumo():
    from models import User
    from models_orders import Order
    from models_songs import Song
    fotos = 0
    if os.path.isdir(paths.IMAGE_FOLDER):
        fotos = sum(len(f) for _, _, f in os.walk(paths.IMAGE_FOLDER))
    return {'musicas': Song.query.count(), 'ordens': Order.query.count(),
            'usuarios': User.query.count(), 'arquivos': fotos}


@backup_bp.route('/backup')
@login_required
def backup_page():
    return render_template('backup.html')


@backup_bp.route('/api/backup/resumo')
@login_required
def api_backup_resumo():
    return jsonify(_resumo())


@backup_bp.route('/api/backup/baixar')
@login_required
def api_backup_baixar():
    fd, caminho = tempfile.mkstemp(prefix='ucontrol-backup-', suffix='.zip')
    os.close(fd)

    @after_this_request
    def _apagar(resposta):
        resposta.call_on_close(lambda: os.path.exists(caminho) and os.remove(caminho))
        return resposta

    criar_backup(caminho)
    nome = f'U-Control-backup-{datetime.date.today().isoformat()}.zip'
    return send_file(caminho, as_attachment=True, download_name=nome, mimetype='application/zip')


@backup_bp.route('/api/backup/restaurar', methods=['POST'])
@login_required
def api_backup_restaurar():
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename:
        return jsonify({'error': 'Escolha o arquivo do backup.'}), 400
    fd, caminho = tempfile.mkstemp(prefix='ucontrol-restaurar-', suffix='.zip')
    os.close(fd)
    try:
        arquivo.save(caminho)
        if not zipfile.is_zipfile(caminho):
            return jsonify({'error': 'Este arquivo não é um backup do U-Control.'}), 400
        manifest = restaurar(caminho)
    except BackupInvalido as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        logging.exception('backup: falha restaurando')
        return jsonify({'error': 'Não deu pra restaurar. O que havia antes foi guardado em instance/backups.'}), 500
    finally:
        os.remove(caminho)
    logging.info('backup: restaurado o backup de %s (versão %s)', manifest.get('criado'), manifest.get('versao'))
    # Os usuários agora são os do backup: entra de novo
    logout_user()
    return jsonify({'ok': True, 'backup': manifest, 'resumo': _resumo()})
