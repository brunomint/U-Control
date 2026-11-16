"""Ordem do culto ao vivo: quando uma ordem muda (editor da ordem, lista
da música, agenda, Bíblia "pôr na ordem", pacote), avisa as páginas
abertas pra elas recarregarem a lista (static/js/ordens_ao_vivo.js).
Antes cada página só lia a ordem ao abrir: quem estava com o painel ou a
/view aberta não via a mudança feita em outro aparelho.

O aviso leva só as datas — o conteúdo cada página busca como já buscava
(as páginas públicas /view e /agenda também recebem)."""
import logging


def avisar(*datas):
    try:
        from extensions import socketio
        socketio.emit('ordens_mudaram', {'datas': [d for d in datas if d]})
    except Exception:   # fora do servidor (scripts/import_orders.py): ninguém pra avisar
        logging.getLogger('ucontrol').debug('ordens_mudaram não enviado', exc_info=True)
