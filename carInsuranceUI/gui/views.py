from django.shortcuts import render
from django.http import HttpResponse
import os, sys
sys.path.append("/Users/annaleontjeva/Software/openalpr/src")
from openalpr import Alpr
import json
import cv2
import pdb

# Create your views here.

def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    #files = json.loads(request.POST["files"])
    for filename, file in request.FILES.items():
        print(filename, file)
        handle_uploaded_file(file, filename)
        image_name = save_first_frame(filename)
        alpr_usage(image_name)

    # call_annas_code:
    # return annas_results 
    return HttpResponse("your files are")

def handle_uploaded_file(file, filename):
    destination_file = open("%s.mov"%filename, 'wb+')
    for chunk in file.chunks():
        destination_file.write(chunk)
    destination_file.close()

def save_first_frame(filename):
    print("%s.mov"%filename)
    vidcap = cv2.VideoCapture("%s.mov"%filename)
    success, image = vidcap.read()
    cv2.imwrite("frame_%s.png" % filename, image)
    return "frame_%s.png" % filename

def alpr_usage(image_name):
    pdb.set_trace()
    alpr = Alpr("eu", "/Users/annaleontjeva/Software/openalpr/config/openalpr.conf", "/Users/annaleontjeva/Software/openalpr/runtime_data")
    if not alpr.is_loaded():
        print("Error loading OpenALPR")
        sys.exit(1)
    alpr.set_top_n(20)
    alpr.set_default_region("md")
    if os.path.isfile(image_name):
        results = alpr.recognize_file(image_name)
        i = 0
        for plate in results['results']:
            i += 1
            print("Plate #%d" % i)
            print("   %12s %12s" % ("Plate", "Confidence"))
            for candidate in plate['candidates']:
                prefix = "-"
                if candidate['matches_template']:
                    prefix = "*"

                print("  %s %12s%12f" % (prefix, candidate['plate'], candidate['confidence']))
    else:
        raise Exception("image file not found")
	
    # Call when completely done to release memory
    alpr.unload()



