"""Agenda de escalas de equipe por data — visão pública (louvor/mídia/
eventos) e páginas privadas de edição/dashboard. `agenda_edit` reusa o
mesmo template `order_edit.html` de blueprints/orders.py (mesmo form).

Um dia pode ter vários cultos: `date` nas rotas é a chave do culto
(YYYY-MM-DD ou YYYY-MM-DD-N, ver orders_store.key_date). A página do dia
mostra todos; louvor/mídia/edição são de um culto; eventos são do dia."""
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from orders_store import day_orders, get_order, key_date, key_seq, load_orders, next_free_key

SECTION_ROUTES = {'louvor': 'agenda.agenda_louvor', 'midia': 'agenda.agenda_midia'}

agenda_bp = Blueprint('agenda', __name__)


@agenda_bp.route("/agenda/hoje")
def agenda_hoje():
    """Redireciona para o próximo culto cadastrado (hoje ou futuro)."""
    from datetime import date as _date, timedelta
    orders = load_orders()
    today = _date.today()
    # Procura até 30 dias à frente
    days_with_data = {key_date(k) for k, o in orders.items() if o}
    for i in range(30):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        if d in days_with_data:
            return redirect(url_for("agenda.agenda_detail", date=d))
    # Nenhum culto cadastrado nos próximos 30 dias
    return render_template("agenda_hoje_vazio.html"), 200


@agenda_bp.route("/agenda")
def agenda_calendar():
    """Calendário de escalas por data"""
    return render_template("agenda_calendar.html")


@agenda_bp.route("/agenda/edit", methods=["GET"])
@login_required
def agenda_edit_selector():
    """Calendário privado para escolher a data e editar a agenda/ordem"""
    return render_template("agenda_calendar_edit.html")


@agenda_bp.route("/agenda/dashboard")
@login_required
def agenda_dashboard():
    """Painel privado de acesso rápido à Agenda de Equipes"""
    return render_template("agenda_dashboard.html")


def _render_day(date, allow_clicks):
    """Página do dia: um bloco por culto (em ordem de horário) e os
    eventos do dia. Chave de 2º culto na URL cai no dia inteiro."""
    day = key_date(date)
    return render_template("agenda_detail.html", date=day, cultos=day_orders(day),
                           eventos=get_order(day).get('eventos', []), allow_clicks=allow_clicks)


def _render_section(date, section):
    """Louvor/mídia de UM culto, com abas pros outros cultos do dia."""
    day = key_date(date)
    cultos = [{'key': k, 'tipo': o.get('tipo') or 'Culto',
               'hora': o.get('horario_culto') or o.get('horario') or ''}
              for k, o in day_orders(day)]
    is_new = not any(c['key'] == date for c in cultos)
    if is_new:
        cultos.append({'key': date, 'tipo': 'Novo culto', 'hora': ''})
    return render_template("agenda_section.html", date=date, day=day, order=get_order(date),
                           section=section, cultos=cultos, is_new=is_new)


@agenda_bp.route("/agenda/<dateslug:date>")
def agenda_detail(date):
    """Detalhe da agenda de um dia (todos os cultos e eventos)"""
    return _render_day(date, allow_clicks=False)


@agenda_bp.route("/agenda/<dateslug:date>/louvor")
def agenda_louvor(date):
    """Página específica para Louvor e Dirigência (de um culto)"""
    return _render_section(date, "louvor")


@agenda_bp.route("/agenda/<dateslug:date>/midia")
def agenda_midia(date):
    """Página específica para Escala de Mídia (de um culto)"""
    return _render_section(date, "midia")


@agenda_bp.route("/agenda/<dateslug:date>/eventos")
def agenda_eventos(date):
    """Página específica para Eventos (do dia — ficam na data pura)"""
    if key_seq(date) > 1:
        return redirect(url_for("agenda.agenda_eventos", date=key_date(date)))
    return render_template("agenda_section.html", date=date, day=date,
                           order=get_order(date), section="eventos", cultos=[])


@agenda_bp.route("/agenda/<dateslug:date>/novo-culto")
@login_required
def agenda_novo_culto(date):
    """Abre o louvor (ou a mídia) de um culto novo nesse dia — a linha só
    é criada quando salvar."""
    endpoint = SECTION_ROUTES.get(request.args.get("secao"), SECTION_ROUTES["louvor"])
    return redirect(url_for(endpoint, date=next_free_key(key_date(date))))


@agenda_bp.route("/agenda/<dateslug:date>/edit")
@login_required
def agenda_edit(date):
    """Rota privada para editar a agenda/ordem de um culto (mesmo form de /order/<date>)"""
    order = get_order(date)
    return render_template("order_edit.html", date=date, order=order or None, is_new=False)


@agenda_bp.route("/agenda/<dateslug:date>/admin")
@login_required
def agenda_detail_admin(date):
    """Detalhe do dia para administradores, com botões de edição"""
    return _render_day(date, allow_clicks=True)
