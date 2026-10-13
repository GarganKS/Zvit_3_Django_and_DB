from django.urls import path

from . import views

urlpatterns = [
    # path("routes/", views.routes),
    path("routes/", views.RoutesListView.as_view()),
    path("trips/", views.trips),
]
