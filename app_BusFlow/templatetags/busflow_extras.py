from django import template

from app_BusFlow.models import Order, Ticket, Trip, Vehicle

register = template.Library()

# Кожен статус має власний колір (клас .badge-<slug> у static/css/style.css).
# Однакові значення в різних моделях ("Заплановано", "Скасовано", "Завершено")
# збігаються за текстом, тому мають однаковий колір.
STATUS_SLUGS = {
    Order.Status.NEW: "new",
    Order.Status.PLANNED: "planned",
    Order.Status.AWAITING: "awaiting",
    Ticket.Status.FREE: "free",
    Ticket.Status.SOLD: "sold",
    Order.Status.REJECTED: "rejected",
    Order.Status.CANCELLED: "cancelled",
    Order.Status.COMPLETED: "done",
    Trip.Status.IN_PROGRESS: "progress",
    Vehicle.Status.WAITING: "free",
    Vehicle.Status.ON_ROUTE: "onroute",
    Vehicle.Status.RENTED: "rented",
    Vehicle.Status.REPAIR: "repair",
    Vehicle.Status.DECOMMISSIONED: "retired",
}


@register.filter
def status_slug(value):
    """Повертає ключ кольору для тексту статусу; невідомий статус - neutral."""
    return STATUS_SLUGS.get(str(value), "neutral")


@register.simple_tag(takes_context=True)
def remove_param(context, key):
    """Поточна адреса списку без параметра key (для кнопки "скинути фільтр")."""
    params = context["request"].GET.copy()
    params.pop(key, None)
    query = params.urlencode()
    return f"{context['request'].path}?{query}" if query else context["request"].path
