"""Conteúdo preparado (preparar/liberar), um conjunto por aparelho (cookie
uc_device, ver display_state): a cifra que o PC do palco prepara não aparece
nem é liberada por outro aparelho, que liberaria com o modo DELE (no culto de
01/11/2026 isso jogava o preparado na tela errada). Chamar dentro de um pedido
ou passar `device`."""
from display_state import current_device
from extensions import db
from models import StagedContent


def _chave(kind, device):
    return (current_device() if device is None else device, kind)


def pegar(kind, device=None):
    return db.session.get(StagedContent, _chave(kind, device))


def salvar(kind, payload, label):
    device, kind = _chave(kind, None)
    item = db.session.get(StagedContent, (device, kind))
    if item is None:
        item = StagedContent(device=device, kind=kind)
        db.session.add(item)
    item.payload = payload
    item.label = label
    db.session.commit()


def apagar(kind, device=None):
    item = pegar(kind, device)
    if item:
        db.session.delete(item)
        db.session.commit()


def do_aparelho(device=None):
    device = current_device() if device is None else device
    return StagedContent.query.filter_by(device=device).all()
