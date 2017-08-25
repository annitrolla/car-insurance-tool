from django.shortcuts import render
import gui.utils as utils


def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    for _, f in request.FILES.items():
        
        # f is the file itself, f.name is the filename
        data = utils.process_file(f, f.name)
        
        # only the first uploaded file is processed
        break    
        
    return render(request, "gui/results.html", data)
