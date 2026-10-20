from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from app_BusFlow.forms import (
    ClientRegisterForm,
    OrderForm,
    OrderPlanForm,
    StopForm,
    TripForm,
    VehicleForm,
    route_formset_class,
)
from app_BusFlow.context_processors import roles
from app_BusFlow.mixins import ClientRequiredMixin, ManagerRequiredMixin, TitleMixin
from app_BusFlow.models import Order, Route, Stop, StopOnRoute, Trip, Vehicle

# Create your views here.


class HomeView(TemplateView):
    """Дашборд: менеджеру - показники й найближчі справи, клієнту - його замовлення."""

    template_name = "app_BusFlow/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = roles(self.request)
        if role["is_manager"]:
            now = timezone.now()
            new_orders = Order.objects.filter(status=Order.Status.NEW)
            context["new_orders_count"] = new_orders.count()
            context["new_orders"] = new_orders.select_related(
                "client__client_profile"
            ).order_by("departure_time")[:5]
            context["trips_today_count"] = (
                Trip.objects.filter(departure_time__date=timezone.localdate())
                .exclude(status=Trip.Status.CANCELLED)
                .count()
            )
            context["free_vehicles_count"] = Vehicle.objects.filter(
                status=Vehicle.Status.WAITING
            ).count()
            context["upcoming_trips"] = (
                Trip.objects.filter(
                    status=Trip.Status.SCHEDULED, departure_time__gte=now
                )
                .select_related("route", "vehicle")
                .prefetch_related("route__stoponroute_set__stop")
                .order_by("departure_time")[:5]
            )
        elif role["is_client"]:
            context["my_orders"] = Order.objects.filter(client=user).select_related(
                "vehicle"
            )[:5]
        return context


class ClientRegisterView(CreateView):
    form_class = ClientRegisterForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Реєстрацію завершено. Увійдіть у систему.")
        return response


# ==================================== Каталог ====================================


class RoutesListView(ManagerRequiredMixin, ListView):
    model = Route
    queryset = Route.objects.prefetch_related(
        Prefetch(
            "stoponroute_set",
            queryset=StopOnRoute.objects.select_related("stop").order_by(
                "stop_sequence"
            ),
        )
    )


class RouteUpdateView(ManagerRequiredMixin, View):
    """Одна сторінка для створення й редагування маршруту (список зупинок)."""

    template_name = "app_BusFlow/route_form.html"
    new_rows = 0  # скільки порожніх рядків зупинок показати

    def get_route(self, pk):
        return get_object_or_404(Route, pk=pk) if pk else Route()

    def build_formset(self, route, data=None):
        formset_class = route_formset_class(extra=2 if not route.pk else self.new_rows)
        queryset = StopOnRoute.objects.order_by("stop_sequence")
        return formset_class(data, instance=route, queryset=queryset)

    def render_form(self, request, route, formset):
        context = {"route": route, "formset": formset, "is_new": not route.pk}
        return render(request, self.template_name, context)

    def get(self, request, pk=None):
        route = self.get_route(pk)
        return self.render_form(request, route, self.build_formset(route))

    def post(self, request, pk=None):
        route = self.get_route(pk)
        is_new = not route.pk
        formset = self.build_formset(route, request.POST)
        if not formset.is_valid():
            return self.render_form(request, route, formset)
        with transaction.atomic():
            route.save()
            formset.save()
        messages.success(
            request, "Маршрут створено." if is_new else "Маршрут збережено."
        )
        return redirect("routes")


class RouteCreateView(RouteUpdateView):
    """Той самий екран, але маршрут у базі з'являється лише після збереження."""


class RouteDeleteView(ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Route
    title = "Видалення маршруту"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("routes")


def matching_ids(model, text, *fields):
    """Первинні ключі записів, де будь-яке з полів містить text без урахування регістру.

    SQLite порівнює регістр лише для латиниці, тому icontains не знайде «київ»
    серед «Київ». Таблиці невеликі, тож порівнюємо в Python.
    """
    needle = text.casefold()
    return [
        row["pk"]
        for row in model.objects.values("pk", *fields)
        if any(needle in (row[field] or "").casefold() for field in fields)
    ]


class TripsListView(LoginRequiredMixin, ListView):
    model = Trip
    periods = (("today", "Сьогодні"), ("upcoming", "Майбутні"), ("past", "Минулі"))

    def get_queryset(self):
        params = self.request.GET
        # Рейси без часів відправлення показуємо в кінці списку.
        queryset = (
            Trip.objects.select_related("route", "vehicle")
            .prefetch_related("route__stoponroute_set__stop")
            .order_by(F("departure_time").asc(nulls_last=True))
        )
        text = params.get("q", "").strip()
        if text:
            stop_ids = matching_ids(Stop, text, "name")
            vehicle_fields = ("name", "plate_number") if roles(self.request)["is_manager"] else ("name",)
            vehicle_ids = matching_ids(Vehicle, text, *vehicle_fields)
            queryset = queryset.filter(
                Q(route__in=Route.objects.filter(stops__in=stop_ids).values("pk"))
                | Q(vehicle__in=vehicle_ids)
            )
        if params.get("status") in Trip.Status.values:
            queryset = queryset.filter(status=params["status"])
        period = params.get("period")
        now = timezone.now()
        if period == "today":
            queryset = queryset.filter(departure_time__date=timezone.localdate())
        elif period == "upcoming":
            queryset = queryset.filter(departure_time__gte=now)
        elif period == "past":
            queryset = queryset.filter(departure_time__lt=now)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context["statuses"] = Trip.Status.choices
        context["periods"] = self.periods
        context["q"] = params.get("q", "").strip()
        context["current_status"] = params.get("status", "")
        context["current_period"] = params.get("period", "")
        context["filtered"] = bool(
            context["q"] or context["current_status"] or context["current_period"]
        )
        return context


class TripCreateView(ManagerRequiredMixin, TitleMixin, CreateView):
    form_class = TripForm
    title = "Додати рейс"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("trips")


class TripUpdateView(ManagerRequiredMixin, TitleMixin, UpdateView):
    model = Trip
    form_class = TripForm
    title = "Редагувати рейс"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("trips")


class TripDeleteView(ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Trip
    title = "Видалення рейсу"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("trips")


class StopsListView(ManagerRequiredMixin, ListView):
    model = Stop
    template_name = "app_BusFlow/stop_list.html"


class StopCreateView(ManagerRequiredMixin, TitleMixin, CreateView):
    form_class = StopForm
    title = "Додати зупинку"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("stops")


class StopUpdateView(ManagerRequiredMixin, TitleMixin, UpdateView):
    model = Stop
    form_class = StopForm
    title = "Редагувати зупинку"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("stops")


class StopDeleteView(ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Stop
    title = "Видалення зупинки"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("stops")


class VehiclesListView(ManagerRequiredMixin, ListView):
    model = Vehicle

    def get_queryset(self):
        params = self.request.GET
        queryset = Vehicle.objects.annotate(trip_count=Count("trip"))
        text = params.get("q", "").strip()
        if text:
            ids = matching_ids(Vehicle, text, "name", "plate_number", "driver")
            queryset = queryset.filter(pk__in=ids)
        if params.get("status") in Vehicle.Status.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context["statuses"] = Vehicle.Status.choices
        context["q"] = params.get("q", "").strip()
        context["current_status"] = params.get("status", "")
        context["filtered"] = bool(context["q"] or context["current_status"])
        return context


class VehicleCreateView(ManagerRequiredMixin, TitleMixin, CreateView):
    form_class = VehicleForm
    title = "Додати транспорт"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("vehicles")


class VehicleUpdateView(ManagerRequiredMixin, TitleMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    title = "Редагувати транспорт"
    template_name = "app_BusFlow/object_form.html"
    success_url = reverse_lazy("vehicles")


class VehicleDeleteView(ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Vehicle
    title = "Видалення транспорту"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("vehicles")


# ==================================== Замовлення ====================================


class OrdersView(LoginRequiredMixin, ListView):
    """Менеджер бачить усі замовлення (+ фільтр за статусом), клієнт - свої."""

    template_name = "app_BusFlow/order_list.html"
    context_object_name = "orders"

    def is_manager(self):
        return self.request.user.groups.filter(name="Менеджери").exists()

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.select_related("client", "vehicle")
        if self.is_manager():
            status = self.request.GET.get("status")
            if status in Order.Status.values:
                queryset = queryset.filter(status=status)
            return queryset
        if hasattr(user, "client_profile"):
            return queryset.filter(client=user)
        raise PermissionDenied

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["is_manager"] = self.is_manager()
        return context


class OrderCreateView(ClientRequiredMixin, CreateView):
    form_class = OrderForm
    template_name = "app_BusFlow/order_form.html"
    success_url = reverse_lazy("orders")

    def form_valid(self, form):
        form.instance.client = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request, "Замовлення надіслано. Очікуйте опрацювання менеджером."
        )
        return response


class OrderPlanView(ManagerRequiredMixin, UpdateView):
    """Планування: клієнтське замовлення стає запланованим, автобус - орендованим."""

    model = Order
    form_class = OrderPlanForm
    template_name = "app_BusFlow/order_plan.html"
    success_url = reverse_lazy("orders")

    def get_queryset(self):
        return Order.objects.filter(status=Order.Status.NEW)

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.status = Order.Status.PLANNED
            self.object.save(update_fields=["status"])
            vehicle = self.object.vehicle
            vehicle.status = Vehicle.Status.RENTED
            vehicle.save(update_fields=["status"])
        messages.success(self.request, "Замовлення заплановано. Автобус зарезервовано.")
        return response


class OrderStatusChangeView(ManagerRequiredMixin, View):
    """Універсальна дія менеджера: відхилення нових і завершення запланованих."""

    template_name = "app_BusFlow/order_action.html"
    from_status = None
    to_status = None
    action_verb = ""
    success_message = ""
    release_vehicle = False

    def get_object(self):
        return get_object_or_404(Order, pk=self.kwargs["pk"], status=self.from_status)

    def get(self, request, pk):
        context = {
            "order": self.get_object(),
            "action": self.action_verb,
            "button": f"Так, {self.action_verb}",
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        order = self.get_object()
        with transaction.atomic():
            order.status = self.to_status
            order.save(update_fields=["status"])
            if self.release_vehicle and order.vehicle_id:
                order.vehicle.status = Vehicle.Status.WAITING
                order.vehicle.save(update_fields=["status"])
        messages.success(request, self.success_message)
        return redirect("orders")


class OrderRejectView(OrderStatusChangeView):
    from_status = Order.Status.NEW
    to_status = Order.Status.REJECTED
    action_verb = "відхилити"
    success_message = "Замовлення відхилено."


class OrderCompleteView(OrderStatusChangeView):
    from_status = Order.Status.PLANNED
    to_status = Order.Status.COMPLETED
    action_verb = "завершити"
    success_message = "Замовлення завершено. Автобус знову вільний."
    release_vehicle = True


class OrderCancelView(LoginRequiredMixin, View):
    """Скасування: клієнт - власне нове замовлення, менеджер - заплановане."""

    template_name = "app_BusFlow/order_action.html"

    def is_manager(self):
        return self.request.user.groups.filter(name="Менеджери").exists()

    def get_object(self):
        user = self.request.user
        if self.is_manager():
            return get_object_or_404(Order, pk=self.kwargs["pk"])
        return get_object_or_404(Order, pk=self.kwargs["pk"], client=user)

    def can_cancel(self, order):
        wanted = Order.Status.PLANNED if self.is_manager() else Order.Status.NEW
        return order.status == wanted

    def get(self, request, pk):
        order = self.get_object()
        if not self.can_cancel(order):
            messages.error(request, "Це замовлення вже не можна скасувати.")
            return redirect("orders")
        context = {
            "order": order,
            "action": "скасувати",
            "button": "Так, скасувати",
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        order = self.get_object()
        if not self.can_cancel(order):
            messages.error(request, "Це замовлення вже не можна скасувати.")
            return redirect("orders")
        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
            # Автобус звільняється, лише якщо це було заплановане замовлення.
            if order.vehicle_id and self.is_manager():
                order.vehicle.status = Vehicle.Status.WAITING
                order.vehicle.save(update_fields=["status"])
        messages.success(request, "Замовлення скасовано.")
        return redirect("orders")
