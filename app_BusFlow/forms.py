from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.utils import timezone

from app_BusFlow.models import ClientProfile, Order


class ClientRegisterForm(UserCreationForm):
    """Реєстрація клієнта: акаунт + група "Клієнти" + профіль організації."""

    organization = forms.CharField(max_length=100, label="Назва організації")
    contact_person = forms.CharField(max_length=100, label="Контактна особа")
    phone = forms.CharField(max_length=20, label="Телефон")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ("email",)

    def save(self, commit=True):
        user = super().save(commit)
        if commit:
            group, _ = Group.objects.get_or_create(name="Клієнти")
            user.groups.add(group)
            ClientProfile.objects.create(
                user=user,
                organization=self.cleaned_data["organization"],
                contact_person=self.cleaned_data["contact_person"],
                phone=self.cleaned_data["phone"],
            )
        return user


class OrderForm(forms.ModelForm):
    """Заявка клієнта на поїздку. Менеджерські поля (vehicle, price) недоступні."""

    class Meta:
        model = Order
        fields = ("direction", "passengers", "departure_time", "comment")
        widgets = {
            "direction": forms.Textarea(attrs={"rows": 2}),
            "departure_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "direction": "Напрямок поїздки",
            "passengers": "Кількість пасажирів",
            "departure_time": "Бажаний час відправлення",
            "comment": "Коментар (побажання)",
        }

    def clean_departure_time(self):
        departure_time = self.cleaned_data["departure_time"]
        if departure_time <= timezone.now():
            raise forms.ValidationError("Час відправлення має бути у майбутньому.")
        return departure_time
