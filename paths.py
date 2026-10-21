"""Onde ficam os arquivos do U-Control.

Dois tipos:
- o que vem com o programa e só é lido (Bíblias, migrations, static/):
  sempre ao lado do código (APP_DIR);
- o que muda em uso (banco e log em instance/, fotos, áudios, QR codes).

Sem UCONTROL_DATA_DIR (Pi, Docker, desenvolvimento) nada muda: instance/
e static/imagens, static/audio, static/qrcodes dentro da pasta do código,
como sempre foi. Com UCONTROL_DATA_DIR (instalação Windows, onde a pasta
do programa em Program Files não aceita escrita e é trocada inteira a
cada atualização) tudo que muda vai pra lá, e main.py continua servindo
nas mesmas URLs /static/imagens/... — os endereços já gravados no banco
(display_state, ordens de culto) valem nos dois casos."""
import os
import sys

# PyInstaller descompacta o programa em sys._MEIPASS; fora dele é a pasta
# deste arquivo (raiz do repositório)
APP_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.environ.get('UCONTROL_DATA_DIR') or None

BIBLES_DIR = os.path.join(APP_DIR, 'bibles')
MIGRATIONS_DIR = os.path.join(APP_DIR, 'migrations')

if DATA_DIR:
    INSTANCE_DIR = os.path.join(DATA_DIR, 'instance')
    IMAGE_FOLDER = os.path.join(DATA_DIR, 'imagens')
    AUDIO_DIR = os.path.join(DATA_DIR, 'audio')
    QRCODE_DIR = os.path.join(DATA_DIR, 'qrcodes')
else:
    INSTANCE_DIR = None  # padrão do Flask: <APP_DIR>/instance
    # Relativo de propósito, como antes: o Pi roda com WorkingDirectory na
    # pasta do código e os testes trocam de pasta (monkeypatch.chdir)
    IMAGE_FOLDER = 'static/imagens'
    AUDIO_DIR = os.path.join(APP_DIR, 'static', 'audio')
    QRCODE_DIR = os.path.join(APP_DIR, 'static', 'qrcodes')

# Pastas servidas em /static/<nome>/ que, com DATA_DIR, saem de lá
SERVED_DATA_DIRS = {
    'imagens': IMAGE_FOLDER,
    'audio': AUDIO_DIR,
    'qrcodes': QRCODE_DIR,
}
