from django.db.models import Prefetch
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
                "route_position"
            ),
        )
    )


class TripsListView(ListView):
    model = Trip
    queryset = Trip.objects.select_related("route")


class VehiclesListView(ListView):
    model = Vehicle
    queryset = Vehicle.objects.select_related("trip__route")


class OrdersView(TemplateView):
    template_name = "app_BusFlow/order_list.html"
