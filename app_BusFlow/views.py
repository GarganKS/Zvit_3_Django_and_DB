from django.contrib import messages
from django.db.models import Count, F, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView

from app_BusFlow.forms import ClientRegisterForm, OrderForm
from app_BusFlow.mixins import ClientRequiredMixin
from app_BusFlow.models import Order, Route, StopOnRoute, Trip, Vehicle

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


class OrdersView(ClientRequiredMixin, ListView):
    """Клієнт бачить лише свої замовлення (менеджерський вигляд - у кроці 6)."""

    template_name = "app_BusFlow/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        return Order.objects.filter(client=self.request.user).select_related("vehicle")


class OrderCreateView(ClientRequiredMixin, CreateView):
    form_class = OrderForm
    template_name = "app_BusFlow/order_form.html"
    success_url = reverse_lazy("orders")

    def form_valid(self, form):
        form.instance.client = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Замовлення надіслано. Очікуйте опрацювання менеджером.")
        return response


class OrderCancelView(ClientRequiredMixin, View):
    """Скасування власного замовлення: GET - сторінка підтвердження, POST - дія."""

    template_name = "app_BusFlow/order_cancel.html"

    def get_object(self):
        return get_object_or_404(Order, pk=self.kwargs["pk"], client=self.request.user)

    def get(self, request, pk):
        order = self.get_object()
        if order.status != Order.Status.NEW:
            messages.error(request, "Скасувати можна лише нове замовлення.")
            return redirect("orders")
        return render(request, self.template_name, {"order": order})

    def post(self, request, pk):
        order = self.get_object()
        if order.status != Order.Status.NEW:
            messages.error(request, "Скасувати можна лише нове замовлення.")
            return redirect("orders")
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        messages.success(request, "Замовлення скасовано.")
        return redirect("orders")
