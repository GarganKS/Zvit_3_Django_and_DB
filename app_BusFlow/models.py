from django.db import models

# Create your models here.


class Stop(models.Model):
    name = models.CharField(max_length=45)

    # coordinates
    def __str__(self):
        return self.name


class Route(models.Model):
    name = models.CharField(max_length=45)
    stops = models.ManyToManyField(Stop, through="StopOnRoute")
    # Зупинки (без розділення на проміжні і головні)
    # Час прибуття і час відправлення

    def __str__(self):
        return self.name


class StopOnRoute(models.Model):
    stop = models.ForeignKey(Stop, models.CASCADE)
    route = models.ForeignKey(Route, models.CASCADE)
    route_position = models.IntegerField()
    # Прибуття і відправлення

    def __str__(self):
        return (
            f"{self.stop.name} - {self.route_position}@{self.route.name}"  # Переробити
        )


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    status = models.CharField(max_length=45)
    price = models.DecimalField(decimal_places=2)
