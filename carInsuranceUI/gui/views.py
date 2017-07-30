from django.shortcuts import render, redirect
from django.http import HttpResponse
import os, sys
import json
import cv2
import subprocess
import glob
import re


# Create your views here.

def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    for filename, f in request.FILES.items():
        handle_uploaded_file(f, f.name)
        image_folder = save_frames(f.name)
        #image_folder = "image_files/IMG_5310/"
        
        for img_file in glob.glob("%s/*" % image_folder):
            results = str(subprocess.check_output(['alpr', '-c', 'eu', img_file]))
            results = results[1:].strip("'").split("\\n")[1:]
            if len(results) > 1:
                m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[0].strip())
                plate_nr, confidence = m.group(1), float(m.group(2))
                if confidence >= 88:
                    best_results = []
                    for i in range(3):
                        m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[i].strip())
                        best_results.append({"plate_nr": m.group(1), "confidence": float(m.group(2))})
                    print(best_results)
                    break
        
        #best_results = [{'confidence': 90.2189, 'plate_nr': '35TVPV'}, {'confidence': 82.2031, 'plate_nr': '3STVPV'}, {'confidence': 78.4793, 'plate_nr': '35TVPY'}]
    return render(request, "gui/results.html", {'results': best_results, 'image_url': img_file})

def handle_uploaded_file(f, filename):
    destination_file = open(filename, 'wb+')
    for chunk in f.chunks():
        destination_file.write(chunk)
    destination_file.close()

def save_frames(filename):
    directory = os.path.join("image_files", filename[:-4])
    if not os.path.exists(directory):
        os.makedirs(directory)
    subprocess.check_output(['ffmpeg','-i', filename, '-vf', 'scale=320:-1', '-r', '10', '-y', os.path.join(directory, "frame_%3d.png")])
    return directory


