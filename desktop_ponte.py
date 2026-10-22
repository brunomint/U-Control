"""Ponte entre o site e o programa da bandeja (desktop.py, só no Windows).

desktop.py registra aqui o que o site pode pedir a ele; no Pi e no Docker
ninguém registra nada, então pode_desligar() é False e o botão "Desligar
o U-Control" nem aparece."""
import threading

_desligar = None


def registrar_desligar(funcao):
    global _desligar
    _desligar = funcao


def pode_desligar():
    return _desligar is not None


def desligar():
    """Desliga daqui a pouco: a resposta da página ainda precisa sair."""
    if _desligar:
        threading.Timer(0.8, _desligar).start()
