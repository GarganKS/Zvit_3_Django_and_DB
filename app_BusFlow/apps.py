from django.apps import AppConfig
from django.db.models.signals import post_migrate

MANAGER_PERMISSION_CODENAMES = [
    "add_route",
    "change_route",
    "delete_route",
    "view_route",
    "add_stop",
    "change_stop",
    "delete_stop",
    "view_stop",
    "add_stoponroute",
    "change_stoponroute",
    "delete_stoponroute",
    "view_stoponroute",
    "add_trip",
    "change_trip",
    "delete_trip",
    "view_trip",
    "add_vehicle",
    "change_vehicle",
    "delete_vehicle",
    "view_vehicle",
    "view_order",
    "change_order",
    "process_order",
]


def ensure_groups(**kwargs):
    """Створює групи ролей і наповнює права менеджера.

    Працює на post_migrate, бо Permission-рядки для нових моделей
    Django створює лише після завершення міграцій. Виконується після
    кожної міграції, але ідемпотентний.
    """
    from django.contrib.auth.models import Group, Permission

    managers, _ = Group.objects.get_or_create(name="Менеджери")
    managers.permissions.set(
        Permission.objects.filter(
            content_type__app_label="app_BusFlow",
            codename__in=MANAGER_PERMISSION_CODENAMES,
        )
    )
    Group.objects.get_or_create(name="Клієнти")


class AppBusflowConfig(AppConfig):
    name = "app_BusFlow"

    def ready(self):
        post_migrate.connect(ensure_groups, sender=self)
