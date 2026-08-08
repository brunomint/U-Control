"""Acesso a ordens de culto — tabelas Order/OrderItem/EventoItem/
OrderTemplate/SectionTemplate (models_orders.py), substituindo
orders.json/order_templates.json/section_templates.json. Usado pelos
blueprints de ordem/agenda e também por view_order_by_date/view_song/
lyrics em main.py (núcleo de display, área de letras — não fazem parte
desta extração).

load_orders()/save_orders() mantêm exatamente o mesmo formato de antes —
dict de dicts por data, no mesmo formato que orders.json produzia (chaves
opcionais omitidas quando ausentes/vazias, igual o código original fazia
com `.pop()`). save_orders(orders) faz sync completo por data, com DIFF
real nas listas-filhas (itens/eventos) — mesmo princípio de songs_store.py:
evita reescrever linhas que não mudaram.

O sistema legado (pré-orders.json, order_of_service.json) foi unificado
na Fase 5.6 — /save e /load (blueprints/orders.py) e o fallback de
view_song (main.py) miram a ordem de hoje (tabela Order) desde então."""
import logging

from extensions import db
from models_orders import EventoItem, Order, OrderItem, OrderTemplate, SectionTemplate

logger = logging.getLogger('ucontrol')


# ---------------------------------------------------------------- itens ---

def _item_kind(item):
    if item.get('isBible'):
        return 'bible'
    if 'anyText' in item and 'url' not in item:
        return 'freetext'
    return 'link'


def _item_to_dict(item):
    if item.kind == 'bible':
        return {'isBible': True, 'reference': item.reference, 'title': item.title}
    if item.kind == 'freetext':
        return {'anyText': item.any_text}
    return {'title': item.title, 'url': item.url}


def _dict_to_item(data, position):
    kind = _item_kind(data)
    if kind == 'bible':
        return OrderItem(position=position, kind=kind, is_bible=True,
                          reference=data.get('reference'), title=data.get('title'))
    if kind == 'freetext':
        return OrderItem(position=position, kind=kind, any_text=data.get('anyText'))
    return OrderItem(position=position, kind=kind, title=data.get('title'), url=data.get('url'))


def _itens_to_dicts(itens):
    return [_item_to_dict(i) for i in itens]


# -------------------------------------------------------------- eventos ---

def _evento_to_dict(e):
    return {'titulo': e.titulo, 'hora': e.hora, 'responsavel': e.responsavel, 'obs': e.obs}


def _eventos_to_dicts(eventos):
    return [_evento_to_dict(e) for e in eventos]


# ---------------------------------------------------------------- order ---

def _order_to_dict(order):
    d = {}
    if order.tipo is not None:
        d['tipo'] = order.tipo
    if order.dirigente is not None:
        d['dirigente'] = order.dirigente
    if order.pregador is not None:
        d['pregador'] = order.pregador
    if order.horario is not None:
        d['horario'] = order.horario
    if order.horario_culto is not None:
        d['horario_culto'] = order.horario_culto
    if order.tema is not None:
        d['tema'] = order.tema
    if order.louvor is not None:
        d['louvor'] = order.louvor
    if order.midia is not None:
        d['midia'] = order.midia
    if order.itens:
        d['itens'] = _itens_to_dicts(order.itens)
    if order.eventos:
        d['eventos'] = _eventos_to_dicts(order.eventos)
    return d


def load_orders():
    """Carrega todas as ordens."""
    orders = Order.query.order_by(Order.date.asc()).all()
    return {o.date: _order_to_dict(o) for o in orders}


def _apply_order_fields(order, data, is_new):
    order.tipo = data.get('tipo')
    order.dirigente = data.get('dirigente')
    order.pregador = data.get('pregador')
    order.horario = data.get('horario')
    order.horario_culto = data.get('horario_culto')
    order.tema = data.get('tema')
    order.louvor = data.get('louvor')
    order.midia = data.get('midia')

    incoming_itens = data.get('itens') or []
    if is_new or incoming_itens != _itens_to_dicts(order.itens):
        order.itens = [_dict_to_item(item, pos) for pos, item in enumerate(incoming_itens)]

    incoming_eventos = data.get('eventos') or []
    if is_new or incoming_eventos != _eventos_to_dicts(order.eventos):
        order.eventos = [
            EventoItem(position=pos, titulo=e.get('titulo'), hora=e.get('hora'),
                       responsavel=e.get('responsavel'), obs=e.get('obs'))
            for pos, e in enumerate(incoming_eventos)
        ]


def save_orders(orders):
    """Salva todas as ordens (sync completo por data, com diff — ver
    docstring do módulo). Retorna True/False, igual antes."""
    try:
        incoming_dates = set(orders.keys())
        existing = {o.date: o for o in Order.query.all()}

        for existing_date, order in existing.items():
            if existing_date not in incoming_dates:
                db.session.delete(order)

        for order_date, data in orders.items():
            order = existing.get(order_date)
            if order is None:
                order = Order(date=order_date)
                db.session.add(order)
                _apply_order_fields(order, data, is_new=True)
            else:
                _apply_order_fields(order, data, is_new=False)

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao salvar orders: {e}")
        return False
    finally:
        db.session.close()


# ----------------------------------------------------------- templates ---

def load_templates():
    templates = OrderTemplate.query.all()
    return {t.name: t.items for t in templates}


def save_templates_file(templates):
    try:
        incoming_names = set(templates.keys())
        existing = {t.name: t for t in OrderTemplate.query.all()}

        for name, tpl in existing.items():
            if name not in incoming_names:
                db.session.delete(tpl)

        for name, items in templates.items():
            tpl = existing.get(name)
            if tpl is None:
                db.session.add(OrderTemplate(name=name, items=items))
            else:
                tpl.items = items

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Erro ao salvar templates: {e}")
        return False
    finally:
        db.session.close()


# --------------------------------------------------- section templates ---

def load_section_templates():
    result = {}
    for st in SectionTemplate.query.all():
        result.setdefault(st.section, {})[st.name] = st.fields
    return result


def save_section_templates(data):
    try:
        incoming_keys = {(section, name) for section, tpls in data.items() for name in tpls}
        existing = {(st.section, st.name): st for st in SectionTemplate.query.all()}

        for key, st in existing.items():
            if key not in incoming_keys:
                db.session.delete(st)

        for section, tpls in data.items():
            for name, fields in tpls.items():
                st = existing.get((section, name))
                if st is None:
                    db.session.add(SectionTemplate(section=section, name=name, fields=fields))
                else:
                    st.fields = fields

        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        db.session.close()
