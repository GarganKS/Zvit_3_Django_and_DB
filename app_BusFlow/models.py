from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# Create your models here.


class Stop(models.Model):
    name = models.CharField(max_length=45)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return self.name


class Route(models.Model):
    stops = models.ManyToManyField(Stop, through="StopOnRoute")
    # === === === === === === === === === === === === #
    # Зупинки (без розділення на проміжні і головні)  #
    # === === === === === === === === === === === === #

    @property
    def display_name(self):
        """Назва маршруту: перша зупинка - остання зупинка."""
        if not self.pk:
            return "Новий маршрут"
        # .all() бере дані з prefetch-кешу, якщо маршрути завантажені заздалегідь.
        links = sorted(self.stoponroute_set.all(), key=lambda link: link.stop_sequence)
        if not links:
            return f"Маршрут #{self.pk}"
        first = links[0].stop.name
        last = links[-1].stop.name
        return first if first == last else f"{first} - {last}"

    def __str__(self):
        return self.display_name


class StopOnRoute(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    stop = models.ForeignKey(Stop, models.CASCADE)
    stop_sequence = models.IntegerField()
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(arrival_time__lte=models.F("departure_time"))
                | models.Q(arrival_time__isnull=True)
                | models.Q(departure_time__isnull=True),
                name="stoponroute_arrival_lte_departure",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.arrival_time
            and self.departure_time
            and self.arrival_time > self.departure_time
        ):
            raise ValidationError(
                {
                    "arrival_time": "Прибуття на зупинці не може бути пізніше відправлення."
                }
            )

    def __str__(self):
        return f"{self.stop_sequence} ({self.stop.name}): {self.route.display_name}"


class Vehicle(models.Model):
    class Status(models.TextChoices):
        WAITING = "Очікує", "Очікує"
        ON_ROUTE = "На рейсі", "На рейсі"
        RENTED = "Орендований", "Орендований"
        REPAIR = "В ремонті", "В ремонті"
        DECOMMISSIONED = "Списано", "Списано"

    name = models.CharField(max_length=45)
    driver = models.CharField(max_length=45, null=True)
    plate_number = models.CharField(max_length=8, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=45, choices=Status.choices, default=Status.WAITING
    )

    class Meta:
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

    route = models.ForeignKey(Route, models.CASCADE)
    status = models.CharField(
        max_length=45, choices=Status.choices, default=Status.SCHEDULED
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE, related_name="trip")
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)

    class Meta:
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


class ClientProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, models.CASCADE, related_name="client_profile"
    )
    organization = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization} ({self.user.username})"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "Нова", "Нова"
        PLANNED = "Заплановано", "Заплановано"
        REJECTED = "Відхилено", "Відхилено"
        CANCELLED = "Скасовано", "Скасовано"
        COMPLETED = "Завершено", "Завершено"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.CASCADE, related_name="orders"
    )
    direction = models.TextField()
    passengers = models.PositiveIntegerField()
    departure_time = models.DateTimeField()
    status = models.CharField(max_length=45, choices=Status.choices, default=Status.NEW)
    comment = models.TextField(blank=True)
    vehicle = models.ForeignKey(
        Vehicle, models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    arrival_time = models.DateTimeField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("process_order", "Може опрацьовувати замовлення"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "Нова",
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
                condition=models.Q(vehicle__isnull=True, price__isnull=True)
                | models.Q(vehicle__isnull=False, price__isnull=False),
                name="order_vehicle_price_together",
            ),
        ]

    def clean(self):
        super().clean()
        if self.passengers is not None and self.passengers <= 0:
            raise ValidationError(
                {"passengers": "Кількість пасажирів має бути більшою за 0."}
            )
        if (
            self.departure_time
            and self.arrival_time
            and self.arrival_time < self.departure_time
        ):
            raise ValidationError(
                {"arrival_time": "Час прибуття не може бути раніше часу відправлення."}
            )
        if self.vehicle and self.passengers and self.vehicle.capacity < self.passengers:
            raise ValidationError(
                {"vehicle": "Місткість автобуса менша за кількість пасажирів."}
            )

    def __str__(self):
        return f"#{self.pk} {self.direction} ({self.status})"
