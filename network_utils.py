"""Porta do servidor e descoberta do IP local na rede — usado tanto por
main.py (geração de QR codes, registro mDNS, banner de start) quanto pelo
blueprint de utilitários (/links). Módulo à parte pelo mesmo motivo de
extensions.py: os blueprints são importados por main.py antes desses
valores serem definidos lá."""
import socket

PORTA = 8585


def obter_endereco_ip():
    # connect() em UDP não manda nada, só escolhe a interface da rota
    # padrão. Sem rede nenhuma (PC da igreja offline, cabo fora) não há
    # rota e dá OSError — antes isso derrubava o programa na abertura
    # (main.py gera os QR codes no import); aí fica só o acesso local.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
