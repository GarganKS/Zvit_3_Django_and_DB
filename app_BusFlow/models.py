from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


def pk_field(column):
    """Первинний ключ INT AUTO_INCREMENT зі стовпцем <таблиця>_id."""
    return models.AutoField(primary_key=True, db_column=column)


class Stop(models.Model):
    id = pk_field("stop_id")
    name = models.CharField(max_length=45)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        db_table = "stop"

    def __str__(self):
        return self.name


class Route(models.Model):
    id = pk_field("route_id")
    name = models.CharField(max_length=45, blank=True)
    stops = models.ManyToManyField(Stop, through="StopOnRoute")

    class Meta:
        db_table = "route"

    def auto_name(self):
        """Назва за зупинками: перша - остання (до 45 символів, як у ERD)."""
        links = sorted(self.stoponroute_set.all(), key=lambda link: link.stop_sequence)
        if not links:
            return ""
        first = links[0].stop.name
        last = links[-1].stop.name
        name = first if first == last else f"{first} - {last}"
        return name[:45]

    @property
    def display_name(self):
        if self.name:
            return self.name
        if not self.pk:
            return "Новий маршрут"
        return self.auto_name() or f"Маршрут #{self.pk}"

    def used_vehicles(self):
        """Автобуси, які їздять цим маршрутом (унікальні, з рейсів)."""
        seen = {}
        for trip in self.trip_set.all():
            seen.setdefault(trip.vehicle_id, trip.vehicle)
        return list(seen.values())

    def __str__(self):
        return self.display_name


class StopOnRoute(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    stop = models.ForeignKey(Stop, models.PROTECT)
    stop_sequence = models.IntegerField()

    class Meta:
        db_table = "stop_on_route"

    def __str__(self):
        return f"{self.stop_sequence} ({self.stop.name}): {self.route.display_name}"


class Vehicle(models.Model):
    class Status(models.TextChoices):
        WAITING = "Очікує", "Очікує"
        ON_ROUTE = "На рейсі", "На рейсі"
        RENTED = "Орендований", "Орендований"
        REPAIR = "В ремонті", "В ремонті"
        DECOMMISSIONED = "Списано", "Списано"

    id = pk_field("vehicle_id")
    name = models.CharField(max_length=45)
    driver = models.CharField(max_length=45, null=True, blank=True)
    plate_number = models.CharField(max_length=8, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=45, choices=Status.choices, default=Status.WAITING
    )

    class Meta:
        db_table = "vehicle"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "Очікує",
                        "На рейсі",
                        "Орендований",
                        "В ремонті",
                        "Списано",
                    ]
                ),
                name="vehicle_status_valid",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.plate_number})"


class Trip(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "Заплановано", "Заплановано"
        IN_PROGRESS = "В дорозі", "В дорозі"
        COMPLETED = "Завершено", "Завершено"
        CANCELLED = "Скасовано", "Скасовано"

    id = pk_field("trip_id")
    route = models.ForeignKey(Route, models.PROTECT)
    status = models.CharField(
        max_length=45, choices=Status.choices, default=Status.SCHEDULED
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    vehicle = models.ForeignKey(Vehicle, models.PROTECT, related_name="trip")
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "trip"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "Заплановано",
                        "В дорозі",
                        "Завершено",
                        "Скасовано",
                    ]
                ),
                name="trip_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(arrival_time__gte=models.F("departure_time"))
                | models.Q(arrival_time__isnull=True)
                | models.Q(departure_time__isnull=True),
                name="trip_arrival_after_departure",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.departure_time
            and self.arrival_time
            and self.arrival_time < self.departure_time
        ):
            raise ValidationError(
                {"arrival_time": "Час прибуття не може бути раніше часу відправлення."}
            )

    def __str__(self):
        return f"{self.route.display_name} ({self.status}): {self.price}"


class Ticket(models.Model):
    """Квиток на рейс. Для кожного рейсу автоматично створюється стільки
    квитків, скільки місць у автобуса (див. signals.py)."""

    class Status(models.TextChoices):
        FREE = "Вільний", "Вільний"
        SOLD = "Продано", "Продано"
        CANCELLED = "Скасовано", "Скасовано"

    id = pk_field("ticket_id")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=45, choices=Status.choices, default=Status.FREE
    )
    trip = models.ForeignKey(Trip, models.CASCADE, related_name="tickets")
    passenger_name = models.CharField(max_length=45, blank=True)
    passenger_phone = models.CharField(max_length=45, blank=True)

    class Meta:
        db_table = "ticket"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["Вільний", "Продано", "Скасовано"]),
                name="ticket_status_valid",
            ),
        ]

    def __str__(self):
        who = f", {self.passenger_name}" if self.passenger_name else ""
        return f"Квиток #{self.pk} ({self.status}{who})"


class Client(models.Model):
    """Клієнт (раніше ClientProfile). Пов'язаний з акаунтом для входу в систему."""

    id = pk_field("client_id")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, models.CASCADE, related_name="client"
    )
    name = models.CharField(max_length=45)
    phone = models.CharField(max_length=45)
    registration_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "client"

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Manager(User):
    class Meta:
        proxy = True
        verbose_name = "менеджер"
        verbose_name_plural = "Менеджери"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "Нова", "Нова"
        AWAITING = "Очікує підтвердження", "Очікує підтвердження"
        PLANNED = "Заплановано", "Заплановано"
        REJECTED = "Відхилено", "Відхилено"
        CANCELLED = "Скасовано", "Скасовано"
        COMPLETED = "Завершено", "Завершено"

    id = pk_field("order_id")
    status = models.CharField(max_length=45, choices=Status.choices, default=Status.NEW)
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    departure_time = models.DateTimeField()
    destination = models.CharField(max_length=45)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.CASCADE, related_name="orders"
    )
    vehicle = models.ForeignKey(
        Vehicle, models.PROTECT, null=True, blank=True, related_name="orders"
    )
    passengers = models.PositiveIntegerField()

    class Meta:
        db_table = "order"
        ordering = ["-id"]
        permissions = [
            ("process_order", "Може опрацьовувати замовлення"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "Нова",
                        "Очікує підтвердження",
                        "Заплановано",
                        "Відхилено",
                        "Скасовано",
                        "Завершено",
                    ]
                ),
                name="order_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(passengers__gt=0),
                name="order_passengers_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(vehicle__isnull=True, total_price__isnull=True)
                | models.Q(vehicle__isnull=False, total_price__isnull=False),
                name="order_vehicle_price_together",
            ),
        ]

    def clean(self):
        super().clean()
        if self.passengers is not None and self.passengers <= 0:
            raise ValidationError(
                {"passengers": "Кількість пасажирів має бути більшою за 0."}
            )
        if self.vehicle and self.passengers and self.vehicle.capacity < self.passengers:
            raise ValidationError(
                {"vehicle": "Місткість автобуса менша за кількість пасажирів."}
            )

    def _move(self, allowed, to_status, **fields):
        if self.status not in allowed:
            raise ValidationError(
                f"Перехід зі статусу «{self.status}» у «{to_status}» неможливий."
            )
        self.status = to_status
        for name, value in fields.items():
            setattr(self, name, value)
        self.save(update_fields=["status", *fields])

    def plan(self, vehicle, total_price):
        """Менеджер опрацював заявку: автобус і ціна призначені, чекаємо клієнта."""
        self._move(
            {self.Status.NEW},
            self.Status.AWAITING,
            vehicle=vehicle,
            total_price=total_price,
        )

    def confirm(self):
        """Клієнт погодився з автобусом і ціною."""
        self._move({self.Status.AWAITING}, self.Status.PLANNED)

    def decline(self):
        """Клієнт відмовився від запропонованих умов."""
        self._move({self.Status.AWAITING}, self.Status.CANCELLED)

    def reject(self):
        self._move({self.Status.NEW}, self.Status.REJECTED)

    def cancel(self, *, by_manager):
        allowed = (
            {self.Status.AWAITING, self.Status.PLANNED}
            if by_manager
            else {self.Status.NEW}
        )
        self._move(allowed, self.Status.CANCELLED)

    def complete(self):
        self._move({self.Status.PLANNED}, self.Status.COMPLETED)

    def __str__(self):
        return f"#{self.pk} {self.destination} ({self.status})"
