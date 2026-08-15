"""Configuração do gunicorn pra produção (usado por ucontrol.sh no Pi).

worker_class="eventlet" + workers=1: main.py mantém ~20 variáveis globais em
memória (estado do ticker, countdown, vídeo, cache de display, clientes
socketio conectados...) sem fila de mensagens compartilhada (Redis etc.).
Mais de um worker faria cada processo ter sua própria cópia desse estado,
quebrando a sincronização entre o painel de controle e as telas. Um
processo só preserva o comportamento de hoje — só troca o servidor WSGI.

Já tentamos "gthread" aqui (combinaria com async_mode='threading' do
main.py, só na teoria) — travava toda requisição HTTP (nem GET / respondia)
rodando de verdade sob gunicorn, achado ao testar o rollout no Pi
(2026-08-15): o gunicorn.conf.py nunca tinha sido validado contra um
gunicorn de verdade antes, só existia como recomendação teórica. A
configuração real de produção no Pi já usava eventlet com sucesso — mantido
aqui como o valor comprovado, não o teórico.

timeout maior que o ping_timeout do socketio (60s, main.py) evita que o
gunicorn mate o worker achando que travou enquanto só tem conexões
WebSocket ociosas em aberto — problema conhecido do Flask-SocketIO com
gunicorn quando o timeout fica curto demais.
"""

bind = "0.0.0.0:8585"
worker_class = "eventlet"
workers = 1
timeout = 120
accesslog = "-"
errorlog = "-"
