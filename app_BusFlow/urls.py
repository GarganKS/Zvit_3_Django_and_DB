from django.contrib.auth import views as auth_views
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    # path("routes/", views.routes),
    path("routes/", views.RoutesListView.as_view(), name="routes"),
    path("routes/new/", views.RouteCreateView.as_view(), name="route_new"),
    path("routes/<int:pk>/edit/", views.RouteUpdateView.as_view(), name="route_edit"),
    path("routes/<int:pk>/delete/", views.RouteDeleteView.as_view(), name="route_delete"),
    # path("trips/", views.trips),
    path("trips/", views.TripsListView.as_view(), name="trips"),
    path("trips/new/", views.TripCreateView.as_view(), name="trip_new"),
    path("trips/<int:pk>/edit/", views.TripUpdateView.as_view(), name="trip_edit"),
    path("trips/<int:pk>/delete/", views.TripDeleteView.as_view(), name="trip_delete"),
    path("stops/", views.StopsListView.as_view(), name="stops"),
    path("stops/new/", views.StopCreateView.as_view(), name="stop_new"),
    path("stops/<int:pk>/edit/", views.StopUpdateView.as_view(), name="stop_edit"),
    path("stops/<int:pk>/delete/", views.StopDeleteView.as_view(), name="stop_delete"),
    path("vehicles/", views.VehiclesListView.as_view(), name="vehicles"),
    path("vehicles/new/", views.VehicleCreateView.as_view(), name="vehicle_new"),
    path("vehicles/<int:pk>/edit/", views.VehicleUpdateView.as_view(), name="vehicle_edit"),
    path("vehicles/<int:pk>/delete/", views.VehicleDeleteView.as_view(), name="vehicle_delete"),
    path("orders/", views.OrdersView.as_view(), name="orders"),
    path("orders/new/", views.OrderCreateView.as_view(), name="order_new"),
    path("orders/<int:pk>/plan/", views.OrderPlanView.as_view(), name="order_plan"),
    path("orders/<int:pk>/reject/", views.OrderRejectView.as_view(), name="order_reject"),
    path("orders/<int:pk>/complete/", views.OrderCompleteView.as_view(), name="order_complete"),
    path("orders/<int:pk>/cancel/", views.OrderCancelView.as_view(), name="order_cancel"),
    # Реєстрація та логін (login/logout/password_change - з django.contrib.auth.urls)
    path("accounts/register/", views.ClientRegisterView.as_view(), name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
]
