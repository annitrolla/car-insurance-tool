from django.shortcuts import render
from django.http import HttpResponse
import os, sys
#sys.path.append("/Users/annaleontjeva/Software/openalpr/src")
#from openalpr import Alpr
import json
import cv2
import subprocess


# Create your views here.

def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    for filename, file in request.FILES.items():
        handle_uploaded_file(file, filename)
        image_name = save_first_frame(filename)
        print(subprocess.check_output(['alpr', image_name]))
    return HttpResponse("your files are")

def handle_uploaded_file(file, filename):
    destination_file = open("%s.mov"%filename, 'wb+')
    for chunk in file.chunks():
        destination_file.write(chunk)
    destination_file.close()

def save_first_frame(filename):
    subprocess.check_output(['ffmpeg','-i', "%s.mov"%filename, '-vframes', '1', '-s', '640x480', '-y', '-f', 'image2', "frame_%s.jpg" % filename])
    #vidcap = cv2.VideoCapture("%s.mov"%filename)
    #success, image = vidcap.read()
    #print(success, image)
    #cv2.imwrite("frame_%s.jpg" % filename, image)
    return "frame_%s.jpg" % filename

"""
def alpr_usage(image_name):
    image_name = "/home/irene/Repos/car-insurance-tool/ea7the.jpg"
    #alpr = Alpr("eu", "/Users/annaleontjeva/Software/openalpr/config/openalpr.conf", "/Users/annaleontjeva/Software/openalpr/runtime_data")
    alpr = Alpr("eu", "/home/irene/Repos/car-insurance-tool/openalpr-master/config/openalpr.conf.user", "/home/irene/Repos/car-insurance-tool/openalpr-master/runtime_data")
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
"""


