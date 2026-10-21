from django.core.management.base import BaseCommand

from app_BusFlow.services import refresh_trip_statuses


class Command(BaseCommand):
    help = "Оновлює статуси рейсів за часом відправлення/прибуття (запускати за розкладом)."

    def handle(self, *args, **options):
        changed = refresh_trip_statuses()
        self.stdout.write(f"Оновлено рейсів: {changed}")
