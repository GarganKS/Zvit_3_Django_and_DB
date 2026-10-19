from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    # path("routes/", views.routes),
    path("routes/", views.RoutesListView.as_view(), name="routes"),
    # path("trips/", views.trips),
    path("trips/", views.TripsListView.as_view(), name="trips"),
    path("vehicles/", views.VehiclesListView.as_view(), name="vehicles"),
    path("orders/", views.OrdersView.as_view(), name="orders"),
    path("orders/new/", views.OrderCreateView.as_view(), name="order_new"),
    path("orders/<int:pk>/cancel/", views.OrderCancelView.as_view(), name="order_cancel"),
    # Реєстрація та логін (login/logout/password_change - з django.contrib.auth.urls)
    path("accounts/register/", views.ClientRegisterView.as_view(), name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
]
