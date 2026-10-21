from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from app_BusFlow.context_processors import roles
from app_BusFlow.forms import (
    ClientRegisterForm,
    OrderForm,
    OrderPlanForm,
    RouteForm,
    StopForm,
    TicketSellForm,
    TripForm,
    VehicleForm,
    route_formset_class,
)
from app_BusFlow.mixins import ClientRequiredMixin, ManagerRequiredMixin, TitleMixin
from app_BusFlow.models import Order, Route, Stop, StopOnRoute, Ticket, Trip, Vehicle
from app_BusFlow.services import refresh_trip_statuses, return_ticket, sell_ticket

# ==================================== Вхід і дашборд ====================================


class RoleLoginView(auth_views.LoginView):
    """Адміністратора після входу одразу відкриває /admin/, решту - дашборд."""

    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        if self.request.user.is_superuser:
            return reverse("admin:index")
        return super().get_default_redirect_url()


class HomeView(TemplateView):
    """Дашборд: менеджеру - показники й найближчі справи, клієнту - його замовлення."""

    template_name = "app_BusFlow/home.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return redirect("admin:index")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = roles(self.request)
        if role["is_manager"]:
            refresh_trip_statuses()
            now = timezone.now()
            orders = Order.objects.select_related("client__client", "vehicle")
            new_orders = orders.filter(status=Order.Status.NEW)
            awaiting = orders.filter(status=Order.Status.AWAITING)
            context["new_orders_count"] = new_orders.count()
            context["awaiting_count"] = awaiting.count()
            context["new_orders"] = new_orders.order_by("departure_time")[:6]
            context["awaiting_orders"] = awaiting.order_by("departure_time")[:6]
            context["trips_today_count"] = (
                Trip.objects.filter(departure_time__date=timezone.localdate())
                .exclude(status=Trip.Status.CANCELLED)
                .count()
            )
            context["trips_in_progress_count"] = Trip.objects.filter(
                status=Trip.Status.IN_PROGRESS
            ).count()
            context["free_vehicles_count"] = Vehicle.objects.filter(
                status=Vehicle.Status.WAITING
            ).count()
            context["upcoming_trips"] = (
                Trip.objects.filter(
                    status=Trip.Status.SCHEDULED, departure_time__gte=now
                )
                .select_related("route", "vehicle")
                .prefetch_related("route__stoponroute_set__stop")
                .order_by("departure_time")[:6]
            )
        elif role["is_client"]:
            mine = Order.objects.filter(client=user).select_related("vehicle")
            context["confirm_orders"] = mine.filter(status=Order.Status.AWAITING)
            context["my_orders"] = mine.exclude(status=Order.Status.AWAITING)[:6]
        return context


class ClientRegisterView(CreateView):
    form_class = ClientRegisterForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Реєстрацію завершено. Увійдіть у систему.")
        return response


class SafeDeleteMixin:
    protected_message = (
        "Цей запис використовується в інших даних, тому його не можна видалити."
    )

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            return redirect(self.get_success_url())


def matching_ids(model, text, *fields):
    needle = text.casefold()
    return [
        row["pk"]
        for row in model.objects.values("pk", *fields)
        if any(needle in (row[field] or "").casefold() for field in fields)
    ]


def int_param(params, key):
    value = params.get(key, "")
    return int(value) if value.isdigit() else None


# ==================================== Маршрути ====================================


class RoutesListView(ManagerRequiredMixin, ListView):
    model = Route

    def get_queryset(self):
        queryset = Route.objects.prefetch_related(
            Prefetch(
                "stoponroute_set",
                queryset=StopOnRoute.objects.select_related("stop").order_by(
                    "stop_sequence"
                ),
            ),
            Prefetch("trip_set", queryset=Trip.objects.select_related("vehicle")),
        )
        stop = int_param(self.request.GET, "stop")
        if stop:
            queryset = queryset.filter(stoponroute__stop_id=stop).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stop = int_param(self.request.GET, "stop")
        context["stop_filter"] = Stop.objects.filter(pk=stop).first() if stop else None
        return context


class RouteDetailView(ManagerRequiredMixin, DetailView):
    model = Route
    template_name = "app_BusFlow/route_detail.html"

    def get_queryset(self):
        return Route.objects.prefetch_related(
            Prefetch(
                "stoponroute_set",
                queryset=StopOnRoute.objects.select_related("stop").order_by(
                    "stop_sequence"
                ),
            ),
            Prefetch("trip_set", queryset=Trip.objects.select_related("vehicle")),
        )


class RouteUpdateView(ManagerRequiredMixin, View):
    """Одна сторінка для створення й редагування маршруту (назва + список зупинок)."""

    template_name = "app_BusFlow/route_form.html"
    new_rows = 0

    def get_route(self, pk):
        return get_object_or_404(Route, pk=pk) if pk else Route()

    def build_formset(self, route, data=None):
        formset_class = route_formset_class(extra=2 if not route.pk else self.new_rows)
        queryset = StopOnRoute.objects.order_by("stop_sequence")
        return formset_class(data, instance=route, queryset=queryset)

    def render_form(self, request, route, form, formset):
        context = {
            "route": route,
            "form": form,
            "formset": formset,
            "is_new": not route.pk,
        }
        return render(request, self.template_name, context)

    def get(self, request, pk=None):
        route = self.get_route(pk)
        return self.render_form(
            request, route, RouteForm(instance=route), self.build_formset(route)
        )

    def post(self, request, pk=None):
        route = self.get_route(pk)
        is_new = not route.pk
        form = RouteForm(request.POST, instance=route)
        formset = self.build_formset(route, request.POST)
        if not (form.is_valid() and formset.is_valid()):
            return self.render_form(request, route, form, formset)
        with transaction.atomic():
            route = form.save()
            formset.save()
            if not route.name:
                links = StopOnRoute.objects.filter(route=route).select_related("stop")
                route = Route.objects.prefetch_related(
                    Prefetch("stoponroute_set", queryset=links)
                ).get(pk=route.pk)
                route.name = route.auto_name()
                route.save(update_fields=["name"])
        messages.success(
            request, "Маршрут створено." if is_new else "Маршрут збережено."
        )
        return redirect("routes")


class RouteCreateView(RouteUpdateView):
    """Той самий екран, але маршрут у базі з'являється лише після збереження."""


class RouteDeleteView(SafeDeleteMixin, ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Route
    title = "Видалення маршруту"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("routes")
    protected_message = (
        "Маршрут не можна видалити: за ним є рейси. Спершу видаліть або змініть їх."
    )


# ==================================== Рейси ====================================


class TripsListView(LoginRequiredMixin, ListView):
    model = Trip
    periods = (("today", "Сьогодні"), ("upcoming", "Майбутні"), ("past", "Минулі"))

    def get_queryset(self):
        refresh_trip_statuses()
        params = self.request.GET
        is_manager = roles(self.request)["is_manager"]
        queryset = (
            Trip.objects.select_related("route", "vehicle")
            .prefetch_related("route__stoponroute_set__stop")
            .annotate(
                tickets_total=Count("tickets", distinct=True),
                tickets_sold=Count(
                    "tickets",
                    filter=Q(tickets__status=Ticket.Status.SOLD),
                    distinct=True,
                ),
            )
            .order_by(F("departure_time").asc(nulls_last=True))
        )
        text = params.get("q", "").strip()
        if text:
            stop_ids = matching_ids(Stop, text, "name")
            vehicle_fields = ("name", "plate_number") if is_manager else ("name",)
            vehicle_ids = matching_ids(Vehicle, text, *vehicle_fields)
            queryset = queryset.filter(
                Q(route__in=Route.objects.filter(stops__in=stop_ids).values("pk"))
                | Q(vehicle__in=vehicle_ids)
            )
        if params.get("status") in Trip.Status.values:
            queryset = queryset.filter(status=params["status"])
        route = int_param(params, "route")
        if route:
            queryset = queryset.filter(route_id=route)
        vehicle = int_param(params, "vehicle")
        if vehicle and is_manager:
            queryset = queryset.filter(vehicle_id=vehicle)
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
        is_manager = roles(self.request)["is_manager"]
        route = int_param(params, "route")
        vehicle = int_param(params, "vehicle") if is_manager else None
        context["statuses"] = Trip.Status.choices
        context["periods"] = self.periods
        context["q"] = params.get("q", "").strip()
        context["current_status"] = params.get("status", "")
        context["current_period"] = params.get("period", "")
        context["route_filter"] = (
            Route.objects.filter(pk=route).first() if route else None
        )
        context["vehicle_filter"] = (
            Vehicle.objects.filter(pk=vehicle).first() if vehicle else None
        )
        context["filtered"] = bool(
            context["q"]
            or context["current_status"]
            or context["current_period"]
            or context["route_filter"]
            or context["vehicle_filter"]
        )
        return context


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "app_BusFlow/trip_detail.html"

    def get_queryset(self):
        return Trip.objects.select_related("route", "vehicle").prefetch_related(
            "route__stoponroute_set__stop"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = dict(self.object.tickets.values_list("status").annotate(n=Count("pk")))
        context["tickets_total"] = sum(counts.values())
        context["tickets_free"] = counts.get("Вільний", 0)
        context["tickets_sold"] = counts.get("Продано", 0)
        if roles(self.request)["is_manager"]:
            context["sold_tickets"] = self.object.tickets.filter(
                status=Ticket.Status.SOLD
            ).order_by("pk")
        context["can_sell"] = (
            self.object.status == Trip.Status.SCHEDULED and context["tickets_free"] > 0
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


class TripDeleteView(SafeDeleteMixin, ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Trip
    title = "Видалення рейсу"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("trips")

    def form_valid(self, form):
        if self.object.tickets.filter(status=Ticket.Status.SOLD).exists():
            messages.error(
                self.request,
                "Рейс не можна видалити: є продані квитки. "
                "Спершу поверніть їх або скасуйте рейс.",
            )
            return redirect("trip_detail", pk=self.object.pk)
        return super().form_valid(form)


class TicketSellView(ManagerRequiredMixin, View):
    template_name = "app_BusFlow/ticket_sell.html"

    def get_trip(self, pk):
        return get_object_or_404(Trip.objects.select_related("route"), pk=pk)

    def get(self, request, pk):
        context = {"trip": self.get_trip(pk), "form": TicketSellForm()}
        return render(request, self.template_name, context)

    def post(self, request, pk):
        trip = self.get_trip(pk)
        form = TicketSellForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"trip": trip, "form": form})
        with transaction.atomic():
            ticket = sell_ticket(trip, **form.cleaned_data)
        if ticket:
            messages.success(
                request, f"Квиток #{ticket.pk} продано: {ticket.passenger_name}."
            )
        else:
            messages.error(
                request,
                "Продаж неможливий: рейс не «Заплановано» або вільних квитків немає.",
            )
        return redirect("trip_detail", pk=trip.pk)


class TicketReturnView(ManagerRequiredMixin, View):
    template_name = "app_BusFlow/ticket_return.html"

    def get_ticket(self, pk):
        return get_object_or_404(Ticket.objects.select_related("trip__route"), pk=pk)

    def get(self, request, pk):
        return render(request, self.template_name, {"ticket": self.get_ticket(pk)})

    def post(self, request, pk):
        ticket = self.get_ticket(pk)
        if return_ticket(ticket):
            messages.success(request, f"Квиток #{ticket.pk} повернуто в продаж.")
        else:
            messages.error(
                request,
                "Повернути можна лише проданий квиток рейсу «Заплановано».",
            )
        return redirect("trip_detail", pk=ticket.trip_id)


# ==================================== Зупинки ====================================


class StopsListView(ManagerRequiredMixin, ListView):
    model = Stop
    template_name = "app_BusFlow/stop_list.html"

    def get_queryset(self):
        return Stop.objects.annotate(
            route_count=Count("stoponroute__route", distinct=True)
        )


class StopDetailView(ManagerRequiredMixin, DetailView):
    model = Stop
    template_name = "app_BusFlow/stop_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["routes"] = Route.objects.filter(
            stoponroute__stop=self.object
        ).distinct()
        return context


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


class StopDeleteView(SafeDeleteMixin, ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Stop
    title = "Видалення зупинки"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("stops")
    protected_message = "Зупинку не можна видалити: вона входить до маршрутів."


# ==================================== Транспорт ====================================


class VehiclesListView(ManagerRequiredMixin, ListView):
    model = Vehicle

    def get_queryset(self):
        refresh_trip_statuses()
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


class VehicleDetailView(ManagerRequiredMixin, DetailView):
    model = Vehicle
    template_name = "app_BusFlow/vehicle_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trips"] = (
            self.object.trip.select_related("route")
            .prefetch_related("route__stoponroute_set__stop")
            .order_by(F("departure_time").desc(nulls_last=True))
        )
        context["orders"] = self.object.orders.select_related("client__client")
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


class VehicleDeleteView(SafeDeleteMixin, ManagerRequiredMixin, TitleMixin, DeleteView):
    model = Vehicle
    title = "Видалення транспорту"
    template_name = "app_BusFlow/confirm_delete.html"
    success_url = reverse_lazy("vehicles")
    protected_message = (
        "Автобус не можна видалити: за ним є рейси або замовлення. "
        "Якщо він більше не використовується, змініть статус на «Списано»."
    )


# ==================================== Замовлення ====================================


class OrdersView(LoginRequiredMixin, ListView):
    template_name = "app_BusFlow/order_list.html"
    context_object_name = "orders"

    def is_manager(self):
        return roles(self.request)["is_manager"]

    def get_queryset(self):
        user = self.request.user
        params = self.request.GET
        queryset = Order.objects.select_related("client__client", "vehicle")
        if self.is_manager():
            if params.get("status") in Order.Status.values:
                queryset = queryset.filter(status=params["status"])
            client = int_param(params, "client")
            if client:
                queryset = queryset.filter(client_id=client)
            vehicle = int_param(params, "vehicle")
            if vehicle:
                queryset = queryset.filter(vehicle_id=vehicle)
            return queryset
        if hasattr(user, "client"):
            return queryset.filter(client=user)
        raise PermissionDenied

    def get_context_data(self, **kwargs):
        from django.contrib.auth.models import User

        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context["statuses"] = Order.Status.choices
        context["current_status"] = params.get("status", "")
        context["is_manager"] = self.is_manager()
        if self.is_manager():
            client = int_param(params, "client")
            vehicle = int_param(params, "vehicle")
            context["client_filter"] = (
                User.objects.select_related("client").filter(pk=client).first()
                if client
                else None
            )
            context["vehicle_filter"] = (
                Vehicle.objects.filter(pk=vehicle).first() if vehicle else None
            )
        return context


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "app_BusFlow/order_detail.html"

    def get_queryset(self):
        queryset = Order.objects.select_related("client__client", "vehicle")
        if roles(self.request)["is_manager"]:
            return queryset
        return queryset.filter(client=self.request.user)


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
    model = Order
    form_class = OrderPlanForm
    template_name = "app_BusFlow/order_plan.html"
    success_url = reverse_lazy("orders")

    def get_queryset(self):
        return Order.objects.filter(status=Order.Status.NEW).select_related(
            "client__client"
        )

    def form_valid(self, form):
        order = self.object
        with transaction.atomic():
            order.plan(form.cleaned_data["vehicle"], form.cleaned_data["total_price"])
        messages.success(
            self.request,
            "Замовлення опрацьовано. Автобус зарезервовано, очікуємо підтвердження клієнта.",
        )
        return redirect(self.get_success_url())


class OrderActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "app_BusFlow/order_action.html"
    role = "manager"
    from_statuses = ()
    action_verb = ""
    success_message = ""
    danger = False

    def test_func(self):
        return roles(self.request)[
            "is_manager" if self.role == "manager" else "is_client"
        ]

    def get_object(self):
        queryset = Order.objects.select_related("vehicle")
        if self.role == "client":
            queryset = queryset.filter(client=self.request.user)
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def apply(self, order):
        raise NotImplementedError

    def allowed(self, order):
        return order.status in self.from_statuses

    def get(self, request, pk):
        order = self.get_object()
        if not self.allowed(order):
            messages.error(
                request, "Цю дію вже не можна виконати для цього замовлення."
            )
            return redirect("orders")
        context = {
            "order": order,
            "action": self.action_verb,
            "button": f"Так, {self.action_verb}",
            "danger": self.danger,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        order = self.get_object()
        if not self.allowed(order):
            messages.error(
                request, "Цю дію вже не можна виконати для цього замовлення."
            )
            return redirect("orders")
        with transaction.atomic():
            self.apply(order)
        messages.success(request, self.success_message)
        return redirect("orders")


class OrderRejectView(OrderActionView):
    from_statuses = (Order.Status.NEW,)
    action_verb = "відхилити"
    success_message = "Замовлення відхилено."
    danger = True

    def apply(self, order):
        order.reject()


class OrderCompleteView(OrderActionView):
    from_statuses = (Order.Status.PLANNED,)
    action_verb = "завершити"
    success_message = "Замовлення завершено. Автобус знову вільний."

    def apply(self, order):
        order.complete()


class OrderCancelView(OrderActionView):
    action_verb = "скасувати"
    success_message = "Замовлення скасовано."
    danger = True

    def test_func(self):
        role = roles(self.request)
        return role["is_manager"] or role["is_client"]

    def is_manager(self):
        return roles(self.request)["is_manager"]

    def get_object(self):
        queryset = Order.objects.select_related("vehicle")
        if not self.is_manager():
            queryset = queryset.filter(client=self.request.user)
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def allowed(self, order):
        wanted = (
            (Order.Status.AWAITING, Order.Status.PLANNED)
            if self.is_manager()
            else (Order.Status.NEW,)
        )
        return order.status in wanted

    def apply(self, order):
        order.cancel(by_manager=self.is_manager())


class OrderConfirmView(OrderActionView):
    role = "client"
    from_statuses = (Order.Status.AWAITING,)
    action_verb = "підтвердити"
    success_message = "Дякуємо! Замовлення підтверджено."

    def apply(self, order):
        order.confirm()


class OrderDeclineView(OrderActionView):
    role = "client"
    from_statuses = (Order.Status.AWAITING,)
    action_verb = "скасувати"
    success_message = "Ви відмовилися від замовлення. Автобус звільнено."
    danger = True

    def apply(self, order):
        order.decline()
