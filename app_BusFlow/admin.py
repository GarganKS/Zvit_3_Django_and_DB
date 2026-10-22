from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User

from app_BusFlow.models import (
    Client,
    Manager,
    Order,
    Route,
    Stop,
    StopOnRoute,
    Ticket,
    Trip,
    Vehicle,
)

MANAGERS_GROUP = "Менеджери"

admin.site.register(Stop)
admin.site.register(Route)
admin.site.register(StopOnRoute)
admin.site.register(Vehicle)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("id", "route", "vehicle", "status", "departure_time", "price")
    list_filter = ("status",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "trip", "price", "status", "passenger_name", "passenger_phone")
    list_filter = ("status",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "user", "registration_date")
    search_fields = ("name", "user__username")
    readonly_fields = ("registration_date",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "client_name",
        "destination",
        "passengers",
        "departure_time",
        "status",
        "vehicle",
        "total_price",
    )
    list_filter = ("status",)
    search_fields = ("destination", "client__username")

    @admin.display(description="Клієнт (назва)")
    def client_name(self, obj):
        profile = getattr(obj.client, "client", None)
        return profile.name if profile else "-"


class ClientInline(admin.StackedInline):
    model = Client
    extra = 0
    fields = ("name", "phone")
    verbose_name_plural = "Дані клієнта (заповнюйте лише для клієнтів)"


class UserAdmin(DjangoUserAdmin):
    """Усі користувачі: роль (групи), ім'я та дані клієнта - вже при створенні."""

    inlines = [ClientInline]
    list_filter = (*DjangoUserAdmin.list_filter, "groups")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
        ("Особисті дані", {"fields": ("first_name", "last_name")}),
        ("Роль", {"fields": ("groups", "is_staff", "is_superuser")}),
    )


@admin.register(Manager)
class ManagerAdmin(DjangoUserAdmin):
    """Окремий розділ "Менеджери": група призначається автоматично,
    тож менеджера не треба створювати, а потім редагувати."""

    list_display = ("username", "first_name", "last_name", "is_active")
    list_filter = ("is_active",)
    filter_horizontal = ()
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
        ("Особисті дані", {"fields": ("first_name", "last_name")}),
    )
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Особисті дані", {"fields": ("first_name", "last_name")}),
        ("Стан", {"fields": ("is_active",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(groups__name=MANAGERS_GROUP)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        group, _ = Group.objects.get_or_create(name=MANAGERS_GROUP)
        obj.groups.add(group)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.site_header = "Адмін-панель BusFlow"
admin.site.site_title = "BusFlow - адмін"
admin.site.index_title = "Керування системою"
