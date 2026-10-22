"""Em que etapa está cada apresentação sendo convertida (gallery.py, em
segundo plano), pra aba Fotos mostrar o andamento e recarregar a galeria
na hora certa (GET /api/conversoes?folder=...).

Etapas: 'slides' (LibreOffice gerando as imagens) -> 'videos' (slides já
na galeria; tirando os vídeos dos slides) ou 'animada' (idem, e gerando a
versão animada) -> 'pronto' | 'erro'.
Só em memória: reiniciar o servidor no meio perde a conversão de qualquer
jeito."""
import threading
import time

GUARDAR = 15 * 60  # conversão terminada some da lista depois disso

_estado = {}  # (pasta, nome) -> {...}
_lock = threading.Lock()


def comecar(pasta, nome, animada):
    with _lock:
        _estado[(pasta, nome)] = {'nome': nome, 'etapa': 'slides', 'animada': animada,
                                  'slides': 0, 'quando': time.time()}


def etapa(pasta, nome, etapa, **dados):
    with _lock:
        item = _estado.get((pasta, nome))
        if item:
            item.update(etapa=etapa, quando=time.time(), **dados)


def da_pasta(pasta):
    agora = time.time()
    with _lock:
        for chave in [k for k, v in _estado.items()
                      if v['etapa'] in ('pronto', 'erro') and agora - v['quando'] > GUARDAR]:
            del _estado[chave]
        return [dict(v) for (p, _), v in _estado.items() if p == pasta]
