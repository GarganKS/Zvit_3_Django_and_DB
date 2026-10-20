from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from app_BusFlow.models import (
    ClientProfile,
    Order,
    Route,
    Stop,
    StopOnRoute,
    Trip,
    Vehicle,
)

# Register your models here.
admin.site.register(Stop)
admin.site.register(Route)
admin.site.register(StopOnRoute)
admin.site.register(Trip)
admin.site.register(Vehicle)


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("organization", "contact_person", "phone", "user", "created_at")
    search_fields = ("organization", "contact_person", "user__username")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "organization",
        "direction",
        "passengers",
        "departure_time",
        "status",
        "vehicle",
        "price",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("direction", "client__username")
    readonly_fields = ("created_at",)

    @admin.display(description="Організація")
    def organization(self, obj):
        profile = getattr(obj.client, "client_profile", None)
        return profile.organization if profile else "-"


class ClientProfileInline(admin.StackedInline):
    model = ClientProfile
    extra = 0


class UserAdmin(DjangoUserAdmin):
    """Користувачі: групи (ролі) вже при створенні + профіль клієнта на сторінці."""

    inlines = [ClientProfileInline]
    list_filter = (*DjangoUserAdmin.list_filter, "groups")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "groups"),
            },
        ),
    )


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

admin.site.site_header = "Адмін-панель BusFlow"
admin.site.site_title = "BusFlow - адмін"
admin.site.index_title = "Керування системою"
