"""Porta do servidor e descoberta do IP local na rede — usado tanto por
main.py (geração de QR codes, registro mDNS, banner de start) quanto pelo
blueprint de utilitários (/links). Módulo à parte pelo mesmo motivo de
extensions.py: os blueprints são importados por main.py antes desses
valores serem definidos lá."""
import socket

PORTA = 8585


def obter_endereco_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip_local = s.getsockname()[0]
    s.close()
    return ip_local
