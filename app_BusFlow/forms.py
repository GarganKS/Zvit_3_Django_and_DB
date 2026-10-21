from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from app_BusFlow.models import (
    Client,
    Order,
    Route,
    Stop,
    StopOnRoute,
    Trip,
    Vehicle,
)


class ClientRegisterForm(UserCreationForm):
    """Реєстрація клієнта: акаунт + група "Клієнти" + запис Client."""

    name = forms.CharField(max_length=45, label="Назва клієнта / організації")
    phone = forms.CharField(max_length=20, label="Телефон")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields

    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            group, _ = Group.objects.get_or_create(name="Клієнти")
            user.groups.add(group)
            Client.objects.create(
                user=user,
                name=self.cleaned_data["name"],
                phone=self.cleaned_data["phone"],
            )
        return user


class OrderForm(forms.ModelForm):
    """Заявка клієнта на поїздку. Менеджерські поля (vehicle, price) недоступні."""

    class Meta:
        model = Order
        fields = ("destination", "passengers", "departure_time")
        widgets = {
            "departure_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "destination": "Напрямок поїздки",
            "passengers": "Кількість пасажирів",
            "departure_time": "Бажаний час відправлення",
        }

    def clean_departure_time(self):
        departure_time = self.cleaned_data["departure_time"]
        if departure_time <= timezone.now():
            raise forms.ValidationError("Час відправлення має бути у майбутньому.")
        return departure_time


class StopForm(forms.ModelForm):
    class Meta:
        model = Stop
        fields = ("name", "address", "latitude", "longitude")


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ("route", "vehicle", "status", "price", "departure_time", "arrival_time")
        widgets = {
            "departure_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "arrival_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "route": "Маршрут",
            "vehicle": "Автобус",
            "price": "Ціна, грн",
            "departure_time": "Час відправлення",
            "arrival_time": "Час прибуття",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["route"].label_from_instance = lambda route: route.display_name
        # Не пропонуємо автобуси в ремонті, списані й орендовані
        # (вже призначений автобус рейсу лишається в списку).
        blocked = (
            Vehicle.Status.REPAIR,
            Vehicle.Status.DECOMMISSIONED,
            Vehicle.Status.RENTED,
        )
        available = Vehicle.objects.exclude(status__in=blocked)
        if self.instance.vehicle_id:
            available = available | Vehicle.objects.filter(pk=self.instance.vehicle_id)
        self.fields["vehicle"].queryset = available.distinct()


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ("name", "driver", "plate_number", "capacity", "status")


class OrderPlanForm(forms.ModelForm):
    """Менеджерська форма планування: автобус і ціна (далі - підтвердження клієнта)."""

    class Meta:
        model = Order
        fields = ("vehicle", "total_price")
        labels = {"vehicle": "Автобус", "total_price": "Ціна, грн"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].required = True
        self.fields["total_price"].required = True
        # Лише вільні автобуси з місткістю не меншою за кількість пасажирів.
        vehicles = Vehicle.objects.filter(status=Vehicle.Status.WAITING)
        if self.instance.passengers:
            vehicles = vehicles.filter(capacity__gte=self.instance.passengers)
        self.fields["vehicle"].queryset = vehicles
        self.fields["vehicle"].label_from_instance = (
            lambda vehicle: f"{vehicle} (місць: {vehicle.capacity})"
        )


class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ("name",)
        labels = {"name": "Назва маршруту"}
        help_texts = {
            "name": "Необов'язково: якщо лишити порожнім - початкова - кінцева зупинка."
        }


class StopOnRouteForm(forms.ModelForm):
    """Рядок зупинки маршруту. Номер у порядку проходження ставить сторінка."""

    class Meta:
        model = StopOnRoute
        fields = ("stop", "stop_sequence")
        widgets = {"stop_sequence": forms.HiddenInput()}
        labels = {"stop": "Зупинка"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Номер не обов'язковий: якщо його немає, береться порядок рядків.
        self.fields["stop_sequence"].required = False
        self.fields["stop"].empty_label = "Оберіть зупинку"


class BaseStopOnRouteFormSet(BaseInlineFormSet):
    MIN_STOPS = 2

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = [
            form
            for form in self.forms
            if form.cleaned_data
            and not self._should_delete_form(form)
            and form.cleaned_data.get("stop")
        ]
        if len(active) < self.MIN_STOPS:
            raise forms.ValidationError(
                "Додайте щонайменше дві зупинки: початкову й кінцеву."
            )
        # Порядок: за номером зі сторінки, а за його відсутності - за порядком рядків.
        ordered = sorted(
            enumerate(active),
            key=lambda item: (
                item[1].cleaned_data.get("stop_sequence") or float("inf"),
                item[0],
            ),
        )
        for number, (_, form) in enumerate(ordered, start=1):
            form.instance.stop_sequence = number


def route_formset_class(extra=0):
    """Формсет зупинок маршруту; extra - скільки порожніх рядків показати."""
    return inlineformset_factory(
        Route,
        StopOnRoute,
        form=StopOnRouteForm,
        formset=BaseStopOnRouteFormSet,
        extra=extra,
        can_delete=True,
    )


class TicketSellForm(forms.Form):
    passenger_name = forms.CharField(max_length=45, label="Ім'я пасажира")
    passenger_phone = forms.CharField(max_length=45, label="Телефон пасажира")
