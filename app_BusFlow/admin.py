from django.contrib import admin

from app_BusFlow.models import Route, Stop, StopOnRoute, Trip, Vehicle

# Register your models here.
admin.site.register(Stop)
admin.site.register(Route)
admin.site.register(StopOnRoute)
admin.site.register(Trip)
admin.site.register(Vehicle)
