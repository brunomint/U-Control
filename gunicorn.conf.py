"""Configuração do gunicorn pra produção (usado por ucontrol.sh no Pi).

worker_class="gthread" + workers=1: main.py mantém ~20 variáveis globais em
memória (estado do ticker, countdown, vídeo, cache de display, clientes
socketio conectados...) sem fila de mensagens compartilhada (Redis etc.).
Mais de um worker faria cada processo ter sua própria cópia desse estado,
quebrando a sincronização entre o painel de controle e as telas. Um
processo só, com várias threads, preserva o comportamento de hoje
(async_mode='threading' em main.py) — só troca o servidor WSGI.

timeout maior que o ping_timeout do socketio (60s, main.py) evita que o
gunicorn mate o worker achando que travou enquanto só tem conexões
WebSocket ociosas em aberto — problema conhecido do Flask-SocketIO com
gunicorn quando o timeout fica curto demais.
"""

bind = "0.0.0.0:8585"
worker_class = "gthread"
workers = 1
threads = 16
timeout = 120
accesslog = "-"
errorlog = "-"
