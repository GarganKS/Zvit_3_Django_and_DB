from django.contrib.auth.models import Group

from app_BusFlow.models import Client

CLIENTS_GROUP = "Клієнти"
MANAGERS_GROUP = "Менеджери"


def assign_client_role(backend, user, response=None, details=None, *args, **kwargs):
    """Крок pipeline social-auth: користувач, який увійшов через Google, - клієнт.

    Додає в групу "Клієнти" і створює запис Client (як при звичайній реєстрації).
    Адміністраторів і менеджерів не чіпає. Ідемпотентний: підходить і для
    нових користувачів, і для тих, хто вже входив через Google раніше.
    """
    if user is None or user.is_superuser:
        return
    if user.groups.filter(name=MANAGERS_GROUP).exists():
        return

    group, _ = Group.objects.get_or_create(name=CLIENTS_GROUP)
    user.groups.add(group)

    if not Client.objects.filter(user=user).exists():
        details = details or {}
        name = (
            details.get("fullname")
            or user.get_full_name()
            or details.get("email")
            or user.username
        )
        Client.objects.create(user=user, name=name[:45], phone="")
