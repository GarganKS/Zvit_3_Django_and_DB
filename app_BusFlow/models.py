from django.db import models

# Create your models here.


class Stop(models.Model):
    name = models.CharField(max_length=45)
    # === ===
    # Адреса
    # === ===

    def __str__(self):
        return self.name


class Route(models.Model):
    name = models.CharField(max_length=45)
    stops = models.ManyToManyField(Stop, through="StopOnRoute")
    # === === === === === === === === === === === === #
    # Зупинки (без розділення на проміжні і головні)  #
    # Час прибуття і час відправлення                 #
    # === === === === === === === === === === === === #

    def __str__(self):
        return self.name


class StopOnRoute(models.Model):
    stop = models.ForeignKey(Stop, models.CASCADE)
    route = models.ForeignKey(Route, models.CASCADE)
    route_position = models.IntegerField()

    def __str__(self):
        return f"{self.route_position} ({self.stop.name}): {self.route.name}"


class Trip(models.Model):
    # === === === === === === #
    # Прибуття і відправлення #
    # === === === === === === #
    route = models.ForeignKey(Route, models.CASCADE)
    status = models.CharField(max_length=45)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.route.name} ({self.status}): {self.price}"


class Vehicle(models.Model):
    name = models.CharField(max_length=45)
    driver = models.CharField(max_length=45)
    plate_number = models.CharField(max_length=15, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=45)
    trip = models.OneToOneField(Trip, models.CASCADE, related_name="vehicle")

    def __str__(self):
        return f"{self.name} ({self.plate_number})"
