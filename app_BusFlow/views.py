from django.views.generic import ListView

from app_BusFlow.models import Route, Trip

# Create your views here.


# def routes(request):
#     return render(request, "app_BusFlow/routes.html")


class RoutesListView(ListView):
    model = Route


class TripsListView(ListView):
    model = Trip
