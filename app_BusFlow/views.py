from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.


def routes(request):
    return HttpResponse("TEST")
    # return render(request, "app_BusFlow/routes.html")
