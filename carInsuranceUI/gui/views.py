from django.shortcuts import render, redirect
from django.http import HttpResponse
import os, sys
import json
import cv2
import subprocess
import glob
import re
import requests


# Create your views here.
VIDEO_DIR = 'video_files'
IMAGE_DIR = 'image_files'

metadata_fields_must_exist = [ "GPS Longitude", "GPS Latitude", "Pixel Aspect Ratio", "Color Representation", "GPS Position",
                              "GPS Coordinates"]
metadata_fields_cant_exist = ["Compressor Name", "Encoder", "Purchase File Format"]
metadata_fields_cant_equal = {"Compatible Brands": 'qt', 'Handler Type': "URL", 'Handler Description': "DataHandler",
                             "Modify Date": "0000:00:00 00:00:00", "Create Date": "0000:00:00 00:00:00"}
metadata_fields_must_be_lte = {"Movie Data Size": 25000000, "File Size": 25, "Duration": 25}

# file size: xx MB, track duration: xx s, 00:00:30 


def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    for _, f in request.FILES.items():
        if not os.path.exists(IMAGE_DIR):
            os.makedirs(IMAGE_DIR)
        if not os.path.exists(VIDEO_DIR):
            os.makedirs(VIDEO_DIR)
        current_image_dir = os.path.join(IMAGE_DIR, f.name[:-4])    
        if not os.path.exists(current_image_dir):
            os.makedirs(current_image_dir)
            
        m = re.match(r"\w*.(\w{3,4})", f.name.lower())
        if m is None:
            return render(request, "gui/results.html", {'results': []}) 
        #elif m.group(1) == 'mov' or m.group(1) == 'mp4':
        else:
            save_video(f, f.name, VIDEO_DIR)
            metadata = video_metadata(os.path.join(VIDEO_DIR, f.name))
            save_frames(os.path.join(VIDEO_DIR, f.name), current_image_dir)
            
        #elif m.group(1) == 'mp4':
        #    save_mp4_to_frames(f, f.name, directory)

        for img_file in glob.glob("%s/*" % current_image_dir):
            print(img_file)
            best_results = recognize_image(img_file, top_best=3, conf_level=88)
            if len(best_results) > 0:
                break
        for car_data in best_results:
            car_data = request_rdw(car_data)
        #best_results = [{'confidence': 90.2189, 'plate_nr': '35TVPV'}, {'confidence': 82.2031, 'plate_nr': '3STVPV'}, {'confidence': 78.4793, 'plate_nr': '35TVPY'}]
    return render(request, "gui/results.html", {'results': best_results, 'image_url': img_file, 'metadata': metadata})

def save_video(f, filename, directory):
    destination_file = open(os.path.join(directory, filename), 'wb+')
    for chunk in f.chunks():
        destination_file.write(chunk)
    destination_file.close()

def video_metadata(filename):
    all_metadata = subprocess.check_output(['exiftool', '-a', '-u', '-g1', filename])
    parts = str(all_metadata).strip().split('\\n')
    metadata = {part.split(" : ")[0].strip(): part.split(" : ")[1].strip() for part in parts if len(part.split(" : ")) > 1}
    
    relevant_metadata = []
        
    for field in metadata_fields_must_exist:
        if field in metadata:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': False})
        else:
            relevant_metadata.append({'key': field, 'value': "-", 'suspicious': True})
    
    for field in metadata_fields_cant_exist:
        if field in metadata:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': True})
        else:
            relevant_metadata.append({'key': field, 'value': "-", 'suspicious': False})
    
    for field, value in metadata_fields_cant_equal.items():
        if field not in metadata:
            relevant_metadata.append({'key': field, 'value': "-", 'suspicious': False})
        elif metadata[field] == value:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': True})
        else:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': False})
     
    field = "Movie Data Size"
    if field in metadata:
        val = int(metadata[field])
        if val > metadata_fields_must_be_lte[field]:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': True})
        else:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': False})
    else:
        relevant_metadata.append({'key': field, 'value': "-", 'suspicious': False})
    
    field = "File Size"
    if field in metadata:
        val = int(metadata[field].split(" ")[0])
        if val > metadata_fields_must_be_lte[field]:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': True})
        else:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': False})
    else:
        relevant_metadata.append({'key': field, 'value': "-", 'suspicious': False})
        
    field = "Duration"
    if field in metadata:
        val = metadata[field].split(" ")
        if len(val) > 1:
            val = float(val[0])
        else:
            val_parts = metadata[field].split(":")
            val = int(val_parts[-1]) + 60 * int(val_parts[-2]) + 60 * int(val_parts[-3])
        if val > metadata_fields_must_be_lte[field]:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': True})
        else:
            relevant_metadata.append({'key': field, 'value': metadata[field], 'suspicious': False})
    else:
        relevant_metadata.append({'key': field, 'value': "-", 'suspicious': False})
        
    return relevant_metadata
    
def save_frames(filepath, directory):
    subprocess.check_output(['ffmpeg','-loglevel', 'panic','-i', filepath, '-vf', 'scale=320:-1', '-r', '10', '-y', os.path.join(directory, "frame_%3d.png")])
       
def recognize_image(filename, top_best=3, conf_level=88):
    results = str(subprocess.check_output(['alpr', '-c', 'eu', filename]))
    results = results[1:].strip("'").split("\\n")[1:]
    best_results = []
    if len(results) > 1:
        m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[0].strip())
        plate_nr, confidence = m.group(1), float(m.group(2))
        if confidence >= conf_level:
            for i in range(top_best):
                m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[i].strip())
                best_results.append({"plate_nr": m.group(1), "confidence": float(m.group(2))})
    return best_results
    
def request_rdw(car_data):
    url = "http://api.datamarket.azure.com/opendata.rdw/VRTG.Open.Data/v1/KENT_VRTG_O_DAT(\'%s\')?$format=json" % car_data['plate_nr']
    r = requests.get(url).json()
    if "error" in r:
        car_data["exists_in_rdw"] = "Does not exist"
        car_data["color"] = "-"
        car_data["brand"] = "-"
    else:
        car_data["exists_in_rdw"] = "Exists"
        car_data["color"] = r["d"]["Eerstekleur"]
        car_data["brand"] = r["d"]["Merk"]
    return car_data


