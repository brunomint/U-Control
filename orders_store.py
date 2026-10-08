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

from sqlalchemy.orm import selectinload

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
    # selectinload evita N+1: sem isso, cada acesso a order.itens/order.eventos
    # em _order_to_dict dispara uma query por ordem — 176 ordens reais viravam
    # 353 queries (1 + 176 + 176), ~1s só pra carregar (mesmo bug e mesma
    # causa raiz do achado em load_songs(), ver songs_store.py — 2026-08-15).
    orders = Order.query.options(
        selectinload(Order.itens), selectinload(Order.eventos)
    ).order_by(Order.date.asc()).all()
    return {o.date: _order_to_dict(o) for o in orders}


def get_order(date):
    """Carrega UMA ordem só, com as mesmas relações eager-loaded de
    load_orders() — usado por /api/orders/<date> POST, que antes chamava
    load_orders() (as 176) só pra achar 1 pela data. Retorna {} se não
    existir (mesmo formato que orders.get(date, {}) que o chamador já
    espera)."""
    order = db.session.get(
        Order, date,
        options=[selectinload(Order.itens), selectinload(Order.eventos)],
    )
    return _order_to_dict(order) if order else {}


def get_next_order(from_date):
    """Primeira ordem com data >= from_date (YYYY-MM-DD) que tenha conteúdo
    — tipo de culto ou itens. O calendário cria linhas vazias pra datas
    sem culto marcado; essas são puladas. Retorna (date, dict) ou
    (None, {}) se não houver nenhuma. Usado pelo card "Próximo culto" do
    dashboard."""
    candidates = Order.query.options(
        selectinload(Order.itens), selectinload(Order.eventos)
    ).filter(Order.date >= from_date).order_by(Order.date.asc()).limit(60)
    for order in candidates:
        if order.tipo or order.itens:
            return order.date, _order_to_dict(order)
    return None, {}


def save_order(date, data):
    """Salva/atualiza/remove UMA ordem só — poucas queries, sem tocar nas
    outras 175. /api/orders/<date> chamava load_orders()+save_orders()
    com o DICT INTEIRO a cada salvamento só pra mudar 1 data — mesma
    causa raiz do achado em touch_last_played()/set_theme()
    (songs_store.py, 2026-08-15), agora pra ordens. `data` vazio ({})
    remove a ordem, igual save_orders() já fazia pra ordem vazia."""
    order = db.session.get(Order, date)
    if not data:
        if order:
            db.session.delete(order)
            db.session.commit()
        return True
    is_new = order is None
    if is_new:
        order = Order(date=date)
        db.session.add(order)
    _apply_order_fields(order, data, is_new)
    db.session.commit()
    return True


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
        # Mesmo motivo do selectinload em load_orders() acima —
        # _apply_order_fields também compara order.itens/order.eventos.
        existing = {
            o.date: o for o in Order.query.options(
                selectinload(Order.itens), selectinload(Order.eventos)
            ).all()
        }

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
