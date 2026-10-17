from django.db.models import Count, F, Prefetch
from django.views.generic import ListView, TemplateView

from app_BusFlow.models import Route, StopOnRoute, Trip, Vehicle

# Create your views here.


class HomeView(TemplateView):
    template_name = "app_BusFlow/home.html"


class RoutesListView(ListView):
    model = Route
    queryset = Route.objects.prefetch_related(
        Prefetch(
            "stoponroute_set",
            queryset=StopOnRoute.objects.select_related("stop").order_by(
                "stop_sequence"
            ),
        )
    )


class TripsListView(ListView):
    model = Trip
    # Рейси без часів відправлення показуємо в кінці списку.
    queryset = Trip.objects.select_related("route", "vehicle").order_by(
        F("departure_time").asc(nulls_last=True)
    )


class VehiclesListView(ListView):
    model = Vehicle
    queryset = Vehicle.objects.annotate(trip_count=Count("trip"))


class OrdersView(TemplateView):
    template_name = "app_BusFlow/order_list.html"
