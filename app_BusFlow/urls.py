from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    # path("routes/", views.routes),
    path("routes/", views.RoutesListView.as_view(), name="routes"),
    # path("trips/", views.trips),
    path("trips/", views.TripsListView.as_view(), name="trips"),
    path("vehicles/", views.VehiclesListView.as_view(), name="vehicles"),
    path("orders/", views.OrdersView.as_view(), name="orders"),
]
