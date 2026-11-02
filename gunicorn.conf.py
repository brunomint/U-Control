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

control_socket_disable: o socket de controle (novo no gunicorn 25) roda numa
thread do processo mestre, que escreve no log bem na hora do fork do worker.
Se o fork pega essa escrita no meio, o worker nasce com a trava do log presa
e para pra sempre em "Booting worker": serviço active, porta aberta, site
fora do ar. Travou 4 de 7 subidas no Pi em nov/2026; num teste isolado, 6 de
45 com o socket ligado e 0 de 45 desligado. Nada aqui usa esse socket.
"""

bind = "0.0.0.0:8585"
worker_class = "gthread"
threads = 100
workers = 1
timeout = 120
accesslog = "-"
errorlog = "-"
control_socket_disable = True
