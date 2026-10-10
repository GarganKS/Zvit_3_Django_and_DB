from django.shortcuts import render

# Create your views here.


def routes(request):
    return render(request, "app_BusFlow/routes.html")


def trips(request):
    return render(request, "app_BusFlow/trips.html")
