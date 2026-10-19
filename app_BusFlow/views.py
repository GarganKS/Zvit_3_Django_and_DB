from django.contrib import messages
from django.db.models import Count, F, Prefetch
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView

from app_BusFlow.forms import ClientRegisterForm
from app_BusFlow.models import Route, StopOnRoute, Trip, Vehicle

# Create your views here.


class HomeView(TemplateView):
    template_name = "app_BusFlow/home.html"


class ClientRegisterView(CreateView):
    form_class = ClientRegisterForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Реєстрацію завершено. Увійдіть у систему.")
        return response


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
    queryset = (
        Trip.objects.select_related("route", "vehicle")
        .prefetch_related("route__stoponroute_set__stop")
        .order_by(F("departure_time").asc(nulls_last=True))
    )


class VehiclesListView(ListView):
    model = Vehicle
    queryset = Vehicle.objects.annotate(trip_count=Count("trip"))


class OrdersView(TemplateView):
    template_name = "app_BusFlow/order_list.html"
