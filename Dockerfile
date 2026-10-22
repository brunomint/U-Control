# Dois alvos a partir da mesma base, mesmo padrão usado no fileswift (outro
# projeto do autor) — a versão do Python fica declarada num lugar só:
#
#   test   docker build --target test .   roda a suíte; não vai pra produção
#   prod   docker build .                 o padrão, e o que o compose usa
#
# Esta é uma FORMA ADICIONAL de rodar o U-Control, não uma substituição do
# fluxo atual no Raspberry Pi (ucontrol.sh + systemd + Cloudflare Tunnel) —
# ver docker-compose.yml pro porquê de network_mode: host.
ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libreoffice: conversão de PPTX->slides na galeria (blueprints/gallery.py).
# ffmpeg: yt-dlp precisa pra extrair/converter áudio em mp3 (blueprints/cifras.py).
# fonts-*: substitutas livres, com as mesmas medidas, de Calibri (Carlito),
# Cambria (Caladea) e Arial/Times/Courier (Liberation) — sem elas o
# LibreOffice troca por fontes mais largas e o texto dos slides quebra.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        fonts-liberation2 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Flask 3.x quebrou a integração com Flask-SocketIO 5.6.0 (RequestContext.session
# virou privado) — patch idempotente, documentado em requirements.txt/KANBAN.md.
COPY scripts/patch_flask_socketio.py scripts/patch_flask_socketio.py
RUN python scripts/patch_flask_socketio.py

FROM base AS test

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .
CMD ["pytest"]

FROM base AS prod

LABEL org.opencontainers.image.title="U-Control" \
      org.opencontainers.image.description="Software de mídia para cultos — Flask + SocketIO" \
      org.opencontainers.image.source="https://github.com/brunomint/U-Control"

COPY . .

EXPOSE 8585

# Segue o mesmo comando que ucontrol.sh já roda no Pi (flask db upgrade,
# depois gunicorn com gunicorn.conf.py) — só sem o prefixo venv/bin/, que
# não existe dentro da imagem.
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8585/login')" || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
