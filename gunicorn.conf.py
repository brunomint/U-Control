"""Configuração do gunicorn pra produção (usado por ucontrol.sh no Pi e
pelo docker-entrypoint.sh).

workers=1: main.py mantém ~20 variáveis globais em memória (estado do
ticker, countdown, vídeo, cache de display, clientes socketio
conectados...) sem fila de mensagens compartilhada (Redis etc.). Mais de
um worker faria cada processo ter sua própria cópia desse estado,
quebrando a sincronização entre o painel de controle e as telas — e o
Socket.IO com mais de um worker ainda precisaria de sticky session.

worker_class="gthread" + threads=100, combinando com async_mode='threading'
do main.py (o mesmo modo do Windows). Até 2026-10 era "eventlet": o
eventlet está só em manutenção e desencoraja uso novo (lembrado num
comentário do TabNews). O gthread já tinha sido tentado em 2026-08 e
"travava toda requisição" — era o padrão de 1 thread só: cada tela
aberta (telão, retorno de palco, celulares) segura uma conexão do
Socket.IO o tempo todo, e a primeira ocupava a única thread. 100 é o
teto, não o que fica aberto: o pool cria as threads conforme as
conexões chegam. Testado com 5 telas, WebSocket de verdade, vídeo e
Tela do PC.

timeout maior que o ping_timeout do socketio (60s, main.py) evita que o
gunicorn mate o worker achando que travou enquanto só tem conexões
WebSocket ociosas em aberto — problema conhecido do Flask-SocketIO com
gunicorn quando o timeout fica curto demais.
"""

bind = "0.0.0.0:8585"
worker_class = "gthread"
threads = 100
workers = 1
timeout = 120
accesslog = "-"
errorlog = "-"
