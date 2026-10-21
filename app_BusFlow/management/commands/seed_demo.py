from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from app_BusFlow.models import Client, Order, Route, Stop, StopOnRoute, Trip, Vehicle


class Command(BaseCommand):
    help = "Створює демонстраційні дані (для порожньої БД після скидання міграцій)."

    def handle(self, *args, **options):
        if Stop.objects.exists():
            self.stdout.write("Дані вже є - нічого не робимо.")
            return
        now = timezone.now()

        def user(username, group, **extra):
            account = User.objects.create_user(username, password="demo12345", **extra)
            account.groups.add(Group.objects.get(name=group))
            return account

        user("manager", "Менеджери", first_name="Олена", last_name="Мельник")
        client_user = user("client", "Клієнти")
        Client.objects.create(user=client_user, name="ТОВ Мандрівник", phone="0501234567")

        stops = {}
        for name, lat, lon in [
            ("Київ", "50.4501", "30.5234"),
            ("Житомир", "50.2547", "28.6587"),
            ("Львів", "49.8397", "24.0297"),
            ("Одеса", "46.4825", "30.7233"),
        ]:
            stops[name] = Stop.objects.create(
                name=name, address=f"Автовокзал, {name}", latitude=lat, longitude=lon
            )
        routes = []
        for names in (["Київ", "Житомир", "Львів"], ["Київ", "Одеса"]):
            route = Route.objects.create(name=f"{names[0]} - {names[-1]}")
            for number, name in enumerate(names, start=1):
                StopOnRoute.objects.create(route=route, stop=stops[name], stop_sequence=number)
            routes.append(route)

        buses = [
            Vehicle.objects.create(name="Bogdan A092", driver="Петро Іваненко", plate_number="AA1234BB", capacity=30),
            Vehicle.objects.create(name="Mercedes Sprinter", driver="Андрій Шевченко", plate_number="KA5678CC", capacity=18),
            Vehicle.objects.create(name="Neoplan", driver=None, plate_number="BC9012DD", capacity=50),
        ]
        Trip.objects.create(
            route=routes[0], vehicle=buses[0], price=Decimal("450"),
            departure_time=now + timedelta(days=1), arrival_time=now + timedelta(days=1, hours=7),
        )
        Trip.objects.create(
            route=routes[1], vehicle=buses[1], price=Decimal("600"),
            departure_time=now + timedelta(days=2), arrival_time=now + timedelta(days=2, hours=8),
        )
        Order.objects.create(
            client=client_user, destination="Карпати", passengers=25,
            departure_time=now + timedelta(days=5),
        )
        self.stdout.write(
            "Готово. Менеджер: manager / demo12345, клієнт: client / demo12345. "
            "Адміна створіть командою createsuperuser."
        )
