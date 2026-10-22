from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from app_BusFlow.models import Order, Trip
from app_BusFlow.services import cancel_free_tickets, generate_tickets, sync_vehicle_status


def _remember_old_vehicle(sender, instance, raw=False, **kwargs):
    """Запам'ятовує автобус до зміни, щоб при заміні звільнити старий."""
    instance._old_vehicle_id = None
    if instance.pk and not raw:
        instance._old_vehicle_id = (
            sender.objects.filter(pk=instance.pk).values_list("vehicle_id", flat=True).first()
        )


pre_save.connect(_remember_old_vehicle, sender=Trip, dispatch_uid="trip_old_vehicle")
pre_save.connect(_remember_old_vehicle, sender=Order, dispatch_uid="order_old_vehicle")


@receiver(post_save, sender=Trip)
def trip_saved(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    sync_vehicle_status(instance.vehicle_id)
    old = getattr(instance, "_old_vehicle_id", None)
    if old and old != instance.vehicle_id:
        sync_vehicle_status(old)
    if created:
        generate_tickets(instance)
    if instance.status == Trip.Status.CANCELLED:
        cancel_free_tickets(instance)


@receiver(post_delete, sender=Trip)
def trip_deleted(sender, instance, **kwargs):
    # Видалений рейс більше не тримає автобус.
    sync_vehicle_status(instance.vehicle_id)


@receiver(post_save, sender=Order)
def order_saved(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sync_vehicle_status(instance.vehicle_id)
    old = getattr(instance, "_old_vehicle_id", None)
    if old and old != instance.vehicle_id:
        sync_vehicle_status(old)


@receiver(post_delete, sender=Order)
def order_deleted(sender, instance, **kwargs):
    sync_vehicle_status(instance.vehicle_id)
