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
        # .all() бере дані з prefetch-кешу, якщо маршрути завантажені заздалегідь.
        links = sorted(self.stoponroute_set.all(), key=lambda link: link.stop_sequence)
        if not links:
            return f"Маршрут #{self.pk}" if self.pk else "Новий маршрут"
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
        if self.arrival_time and self.departure_time and self.arrival_time > self.departure_time:
            raise ValidationError(
                {"arrival_time": "Прибуття на зупинці не може бути пізніше відправлення."}
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

    # === === === === === === #
    # Прибуття і відправлення #
    # === === === === === === #
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
        if self.departure_time and self.arrival_time and self.arrival_time < self.departure_time:
            raise ValidationError(
                {"arrival_time": "Час прибуття не може бути раніше часу відправлення."}
            )

    def __str__(self):
        return f"{self.route.display_name} ({self.status}): {self.price}"
