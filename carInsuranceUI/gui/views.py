from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
import os, sys
import json
import cv2
import subprocess
import glob
import re
import requests
import numpy as np


# Create your views here.
VIDEO_DIR = 'video_files'
IMAGE_DIR = 'image_files'

MAX_RESULTS = 3
CONF_LEVEL = 80

RDW_URL_TEMPLATE = "http://api.datamarket.azure.com/opendata.rdw/VRTG.Open.Data/v1/KENT_VRTG_O_DAT(\'%s\')?$format=json"

warped_img_margin = 50

metadata_fields_must_exist = [ "GPS Longitude", "GPS Latitude", "Pixel Aspect Ratio", "Color Representation", "GPS Position",
                              "GPS Coordinates"]
metadata_fields_cant_exist = ["Compressor Name", "Encoder", "Purchase File Format"]
metadata_fields_cant_equal = {"Compatible Brands": 'qt', 'Handler Type': "URL", 'Handler Description': "DataHandler",
                             "Modify Date": "0000:00:00 00:00:00", "Create Date": "0000:00:00 00:00:00"}
metadata_fields_must_be_lte = {"Movie Data Size": 25000000, "File Size": 25, "Duration": 25}


def index(request):
    return render(request, "gui/index.html")


def recognize_car_plate(request):
    
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
    if not os.path.exists(VIDEO_DIR):
        os.makedirs(VIDEO_DIR)
            
    for _, f in request.FILES.items():
        
        filename = f.name
        file_basename, file_extension = os.path.splitext(filename)
        file_extension = file_extension.lower()
            
        # uploaded file is an image file
        if file_extension in ['.jpg', '.jpeg', '.png']:
            # save image
            _save_image(f, filename, file_basename)
            current_image_dir = os.path.join(IMAGE_DIR, file_basename)
            
            # get image metadata using exiftool
            metadata = _get_metadata(os.path.join(current_image_dir, filename))
            
            # convert to png if necessary (alpr works better with png than with jpg)
            if file_extension != ".png":
                subprocess.check_output(['mogrify', '-format', 'png', os.path.join(current_image_dir, filename)])
            filename = file_basename + ".png"
            img_file = os.path.join(current_image_dir, filename)
            
            # use alpr to recognize licence plates from the image
            best_results = _recognize_image(img_file, top_best=MAX_RESULTS, conf_level=CONF_LEVEL)
            
            # if no results are found, try rotating the image
            rotations = 0
            while len(best_results) == 0 and rotations < 3:
                subprocess.check_output(['mogrify', '-rotate', '90', img_file])
                rotations += 1
                best_results = _recognize_image(img_file, top_best=MAX_RESULTS, conf_level=CONF_LEVEL)
        
        # uploaded file is a video file
        else:
            # create directory for video frames
            current_image_dir = os.path.join(IMAGE_DIR, file_basename)    
            if not os.path.exists(current_image_dir):
                os.makedirs(current_image_dir)
            
            # save video
            _save_video(f, filename, VIDEO_DIR)
            
            # get video metadata using exiftool
            metadata = _get_metadata(os.path.join(VIDEO_DIR, filename))
            
            # extract frames from video using ffmpeg
            _save_frames(os.path.join(VIDEO_DIR, f.name), current_image_dir)
            
            # use alpr to recognize licence plates from the video frames
            for img_file in glob.glob("%s/*" % current_image_dir):
                print(img_file)
                
                # try on the original image
                best_results = _recognize_image(img_file, top_best=MAX_RESULTS, conf_level=CONF_LEVEL)
                if len(best_results) > 0:
                    break
                    
                # preprocess the image and try again
                image = cv2.imread(img_file)
                screenCnt = _get_edges(image)
                if screenCnt is None:
                    print("No 4-cornered contour found")
                else:
                    warp = _process_rect(image, screenCnt)
                    warp_padded = cv2.copyMakeBorder(warp, warped_img_margin, warped_img_margin, warped_img_margin,
                                                     warped_img_margin, cv2.BORDER_CONSTANT)
                    cv2.imwrite(os.path.join(current_image_dir, 'warped.png'), warp_padded)
                    
                    best_results = _recognize_image(os.path.join(current_image_dir, 'warped.png'), top_best=MAX_RESULTS,
                                                    conf_level=CONF_LEVEL)
                if len(best_results) > 0:
                    break
                
        # check RDW to see if the found plate numbers actually exist
        for car_data in best_results:
            print(car_data)
            car_data = _request_rdw(car_data)
            
            # try replacing "J" with "4" (alpr tends to mistake "4" for "J")
            # NOTE: the following solution replaces all "J"-s in the found plate number, but for comprehensiveness, one could try replacing any combination of "J"-s (e.g. replacing only the first occurrence of "J")
            if car_data['exists_in_rdw'] != "Exists" and "J" in car_data['plate_nr']:
                car_data2 = car_data.copy()
                car_data2['plate_nr'] = car_data2['plate_nr'].replace("J", "4")
                car_data2 = _request_rdw(car_data2)
                if car_data2['exists_in_rdw'] == "Exists":
                    car_data = car_data2.copy()
                    
        # only the first uploaded file is processed
        break    
        
    return render(request, "gui/results.html", {'results': best_results, 'image_url': img_file, 'metadata': metadata})

def _save_video(f, filename, directory):
    destination_file = open(os.path.join(directory, filename), 'wb+')
    for chunk in f.chunks():
        destination_file.write(chunk)
    destination_file.close()
    
def _save_image(f, filename, directory):
    fs = FileSystemStorage()
    fs.save(os.path.join(directory, filename), f)
    
def _save_frames(filepath, directory):
    subprocess.check_output(['ffmpeg','-loglevel', 'panic','-i', filepath, '-vf', 'scale=320:-1', '-r', '10', '-y', os.path.join(directory, "frame_%3d.png")])
       
def _recognize_image(filename, top_best=5, conf_level=88):
    results = str(subprocess.check_output(['alpr', '-c', 'eu', filename]))
    results = results[1:].strip("'").split("\\n")[1:]
    best_results = []
    if len(results) > 1:
        m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[0].strip())
        plate_nr, confidence = m.group(1), float(m.group(2))
        if confidence >= conf_level:
            for res in results:
                m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", res.strip())
                if m:
                    plate_nr = m.group(1)
                    conf = float(m.group(2))
                    if len(plate_nr) == 6:
                        best_results.append({"plate_nr": plate_nr, "confidence": conf})
                    if len(best_results) >= top_best:
                        break
    return best_results
    
def _request_rdw(car_data):
    url = RDW_URL_TEMPLATE % car_data['plate_nr']
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

def _get_metadata(filename):
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
        val = float(metadata[field].split(" ")[0])
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
    
def _get_edges(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray, 30, 200)
    # find contours in the edged image, keep only the largest
    # ones, and initialize our screen contour
    (_,cnts, _) = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key = cv2.contourArea, reverse = True)
    screenCnt = None
    # loop over our contours
    for c in cnts:
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        # if our approximated contour has four points, then
        # we can assume that we have found our screen
        if len(approx) == 4:
            screenCnt = approx
            return screenCnt
    return None
        
        
def _process_rect(image, screenCnt):
    pts = screenCnt.reshape(4, 2)
    rect = np.zeros((4, 2), dtype = "float32")

    # the top-left point has the smallest sum whereas the
    # bottom-right has the largest sum
    s = pts.sum(axis = 1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # compute the difference between the points -- the top-right
    # will have the minumum difference and the bottom-left will
    # have the maximum difference
    diff = np.diff(pts, axis = 1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # multiply the rectangle by the original ratio
    #rect *= ratio
    
    # now that we have our rectangle of points, let's compute
    # the width of our new image
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))

    # ...and now for the height of our new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))

    # take the maximum of the width and height values to reach
    # our final dimensions
    maxWidth = max(int(widthA), int(widthB))
    maxHeight = max(int(heightA), int(heightB))

    # construct our destination points which will be used to
    # map the screen to a top-down, "birds eye" view
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype = "float32")

    # calculate the perspective transform matrix and warp
    # the perspective to grab the screen
    M = cv2.getPerspectiveTransform(rect, dst)
    warp = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warp
