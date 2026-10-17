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
        links = list(self.stoponroute_set.order_by("stop_sequence"))
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

    def __str__(self):
        return f"{self.stop_sequence} ({self.stop.name}): {self.route.display_name}"


class Vehicle(models.Model):
    name = models.CharField(max_length=45)
    driver = models.CharField(max_length=45, null=True)
    plate_number = models.CharField(max_length=15, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=45)

    def __str__(self):
        return f"{self.name} ({self.plate_number})"


class Trip(models.Model):
    # === === === === === === #
    # Прибуття і відправлення #
    # === === === === === === #
    route = models.ForeignKey(Route, models.CASCADE)
    status = models.CharField(max_length=45)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    vehicle = models.OneToOneField(Vehicle, models.CASCADE, related_name="trip")

    def __str__(self):
        return f"{self.route.display_name} ({self.status}): {self.price}"
