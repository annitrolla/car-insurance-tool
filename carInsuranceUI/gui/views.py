from django.shortcuts import render
from django.http import HttpResponse
import json

# Create your views here.

def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
	#files = json.loads(request.POST["files"])
	print(request)
	return HttpResponse("your files are")
