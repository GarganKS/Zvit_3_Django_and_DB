from django.shortcuts import render
from django.views.generic import ListView

from app_BusFlow.models import Route

# Create your views here.


# def routes(request):
#     return render(request, "app_BusFlow/routes.html")


class RoutesListView(ListView):
    model = Route


def trips(request):
    return render(request, "app_BusFlow/trips.html")
