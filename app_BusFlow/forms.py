from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User

from app_BusFlow.models import ClientProfile


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
