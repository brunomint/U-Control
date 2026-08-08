"""Agenda de escalas de equipe por data — visão pública (louvor/mídia/
eventos) e páginas privadas de edição/dashboard. `agenda_edit` reusa o
mesmo template `order_edit.html` de blueprints/orders.py (mesmo form)."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required

from orders_store import load_orders

agenda_bp = Blueprint('agenda', __name__)


@agenda_bp.route("/agenda/hoje")
def agenda_hoje():
    """Redireciona para o próximo culto cadastrado (hoje ou futuro)."""
    from datetime import date as _date, timedelta
    orders = load_orders()
    today = _date.today()
    # Procura até 30 dias à frente
    for i in range(30):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        if d in orders and orders[d]:
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


@agenda_bp.route("/agenda/<dateslug:date>")
def agenda_detail(date):
    """Detalhe da agenda de uma data específica"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_detail.html", date=date, order=order, allow_clicks=False)


@agenda_bp.route("/agenda/<dateslug:date>/louvor")
def agenda_louvor(date):
    """Página específica para Louvor e Dirigência"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="louvor")


@agenda_bp.route("/agenda/<dateslug:date>/midia")
def agenda_midia(date):
    """Página específica para Escala de Mídia"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="midia")


@agenda_bp.route("/agenda/<dateslug:date>/eventos")
def agenda_eventos(date):
    """Página específica para Eventos"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_section.html", date=date, order=order, section="eventos")


@agenda_bp.route("/agenda/<dateslug:date>/edit")
@login_required
def agenda_edit(date):
    """Rota privada para editar a agenda/ordem de uma data (mesmo form de /order/<date>)"""
    orders = load_orders()
    order = orders.get(date)
    return render_template("order_edit.html", date=date, order=order, is_new=False)


@agenda_bp.route("/agenda/<dateslug:date>/admin")
@login_required
def agenda_detail_admin(date):
    """Detalhe da agenda para administradores, com cards clicáveis"""
    orders = load_orders()
    order = orders.get(date, {})
    return render_template("agenda_detail.html", date=date, order=order, allow_clicks=True)
