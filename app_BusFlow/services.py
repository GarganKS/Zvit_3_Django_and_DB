"""Автоматизації: статуси автобусів, рейсів і квитків."""

from django.db import transaction
from django.utils import timezone

from app_BusFlow.models import Order, Ticket, Trip, Vehicle

# Ці статуси менеджер ставить вручну - автоматика їх не чіпає.
MANUAL_VEHICLE_STATUSES = (Vehicle.Status.REPAIR, Vehicle.Status.DECOMMISSIONED)


def sync_vehicle_status(vehicle_id):
    """Виставляє статус автобуса за його поточними замовленнями та рейсами.

    1. У ремонті / списаний - не змінюється.
    2. Є замовлення «Очікує підтвердження» чи «Заплановано» - «Орендований».
    3. Є рейс «В дорозі» - «На рейсі».
    4. Інакше - «Очікує» (вільний).
    """
    if not vehicle_id:
        return
    vehicle = Vehicle.objects.filter(pk=vehicle_id).first()
    if vehicle is None or vehicle.status in MANUAL_VEHICLE_STATUSES:
        return
    active_orders = Order.objects.filter(
        vehicle=vehicle,
        status__in=(Order.Status.AWAITING, Order.Status.PLANNED),
    )
    if active_orders.exists():
        target = Vehicle.Status.RENTED
    elif Trip.objects.filter(vehicle=vehicle, status=Trip.Status.IN_PROGRESS).exists():
        target = Vehicle.Status.ON_ROUTE
    else:
        target = Vehicle.Status.WAITING
    if target != vehicle.status:
        # update(), а не save(): без зайвих сигналів і гонок з іншими полями.
        Vehicle.objects.filter(pk=vehicle.pk).update(status=target)


def generate_tickets(trip):
    """Створює для нового рейсу вільні квитки за місткістю автобуса."""
    Ticket.objects.bulk_create(
        [Ticket(trip=trip, price=trip.price) for _ in range(trip.vehicle.capacity)]
    )


def cancel_free_tickets(trip):
    trip.tickets.filter(status=Ticket.Status.FREE).update(status=Ticket.Status.CANCELLED)


def refresh_trip_statuses():
    """Рейси за розкладом: «Заплановано» -> «В дорозі» -> «Завершено».

    Рейси без часів не змінюються. Зміна йде через save(), тож статуси
    автобусів оновлюються сигналами. Викликається при відкритті дашборду,
    списків і командою `manage.py update_statuses`. Повертає кількість змін.
    """
    now = timezone.now()
    changed = 0
    with transaction.atomic():
        started = Trip.objects.filter(
            status=Trip.Status.SCHEDULED, departure_time__lte=now
        )
        for trip in started:
            done = trip.arrival_time and trip.arrival_time <= now
            trip.status = Trip.Status.COMPLETED if done else Trip.Status.IN_PROGRESS
            trip.save(update_fields=["status"])
            changed += 1
        for trip in Trip.objects.filter(
            status=Trip.Status.IN_PROGRESS, arrival_time__lte=now
        ):
            trip.status = Trip.Status.COMPLETED
            trip.save(update_fields=["status"])
            changed += 1
    return changed
