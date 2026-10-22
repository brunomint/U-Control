"""Ponte entre o site e o programa da bandeja (desktop.py, só no Windows).

desktop.py registra aqui o que o site pode pedir a ele; no Pi e no Docker
ninguém registra nada, então pode_desligar() é False e o botão "Desligar
o U-Control" nem aparece, e o site no telão (navegador_telao.py) fica
indisponível."""
import threading

_desligar = None
_janelas = {}  # navegador / monitor_telao: funções do desktop.py; perfil_site: pasta


def registrar_desligar(funcao):
    global _desligar
    _desligar = funcao


def pode_desligar():
    return _desligar is not None


def desligar():
    """Desliga daqui a pouco: a resposta da página ainda precisa sair."""
    if _desligar:
        threading.Timer(0.8, _desligar).start()


def registrar_janelas(navegador, monitor_telao, perfil_site):
    """Pro site no telão (navegador_telao.py): achar o Chrome/Edge, o
    monitor do datashow e a pasta do perfil do navegador do site."""
    _janelas.update(navegador=navegador, monitor_telao=monitor_telao, perfil_site=perfil_site)


def navegador():
    return _janelas['navegador']() if 'navegador' in _janelas else None


def monitor_telao():
    return _janelas['monitor_telao']() if 'monitor_telao' in _janelas else None


def perfil_site():
    return _janelas.get('perfil_site')
