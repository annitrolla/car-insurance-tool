from django.core.files.storage import FileSystemStorage
import os, sys
import json
import cv2
import subprocess
import glob
import re
import requests
import numpy as np

VIDEO_DIR = 'video_files'
IMAGE_DIR = 'image_files'

MAX_RESULTS = 3 # up to this many results are shown in the UI
CONF_LEVEL = 80 # the video frames (images) are iterated as long as the model finds at least one result (possible license plate number) with confidence >= CONF_LEVEL

# the URL template for making requests to the RDW API. The licence plate number is substituted later in place of "%s".
RDW_URL_TEMPLATE = "http://api.datamarket.azure.com/opendata.rdw/VRTG.Open.Data/v1/KENT_VRTG_O_DAT(\'%s\')?$format=json"

warped_img_margin = 50 # when image is preprocessed (licence plate detected and cropped from the image), this many pixels are used to "pad" the cropped license plate

# the following are metedata constraints, used to determine if the uploaded file is "suspicious" (i.e. manipulated) or not
metadata_fields_must_exist = [ "GPS Longitude", "GPS Latitude", "Pixel Aspect Ratio", "Color Representation", "GPS Position",
                              "GPS Coordinates"]
metadata_fields_cant_exist = ["Compressor Name", "Encoder", "Purchase File Format"]
metadata_fields_cant_equal = {"Compatible Brands": 'qt', 'Handler Type': "URL", 'Handler Description': "DataHandler",
                             "Modify Date": "0000:00:00 00:00:00", "Create Date": "0000:00:00 00:00:00"}
metadata_fields_must_be_lte = {"Movie Data Size": 25000000, "File Size": 25, "Duration": 25}


def process_file(f, filename):
    """
    1. If necessary, creates directories for:
       1) Saving the video files.
       2) Saving the frames (images) extracted from the video.
    2. Processes the uploaded file, depending on whether it is an image file or a video file.
    3. Checks if the found results (possible licence plate numbers) exist in the RDW database.
    4. Returns the "best" results, the image/frame that was used to find these results and the metadata of the uploaded file.
    """
    
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
    if not os.path.exists(VIDEO_DIR):
        os.makedirs(VIDEO_DIR)
    
    try:
        file_basename, file_extension = os.path.splitext(filename)
        file_extension = file_extension.lower()
        file_basename = file_basename.replace("]", "").replace("[", "")

        # uploaded file is an image file
        if file_extension in ['.jpg', '.jpeg', '.png']:
            best_results, img_file, metadata = _process_image(f, filename, file_basename)

        # uploaded file is a video file
        else:
            best_results, img_file, metadata = _process_video(f, filename, file_basename)

        # check RDW to see if the found plate numbers actually exist
        best_results = _add_rdw_data(best_results)
    
        return {'results': best_results, 'image_url': img_file, 'metadata': metadata, 'file_corrupt': False}
    
    except subprocess.CalledProcessError: # uploaded file is not a valid image/video file
        return {'results': None, 'image_url': None, 'metadata': None, 'file_corrupt': True}
                
def _process_image(f, filename, file_basename):
    """
    1. Saves the image.
    2. Extracts metadata.
    3. If the image was in jpg format, converts it to png (png works better with alpr)
    4. Tries to find results (possible licence plate numbers) using:
       1) the original image
       2) the rotated image (sometimes the conversion from jpg to png rotates the image, but for alpr the image needs to be straight).
    """
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
        
    return best_results, img_file, metadata

def _process_video(f, filename, file_basename):
    """
    1. Saves the video.
    2. Extracts metadata.
    3. Extracts frames from the video.
    4. Loops over the frames and tries to find results (possible licence plate numbers) using:
       1) the original frame
       2) the preprocessed frame (where the licence plate is detected from the image and brought into perspective).
    """
            
    # save video
    _save_video(f, filename, VIDEO_DIR)
            
    # get video metadata using exiftool
    metadata = _get_metadata(os.path.join(VIDEO_DIR, filename))
            
    # create directory for video frames
    current_image_dir = os.path.join(IMAGE_DIR, file_basename)    
    if not os.path.exists(current_image_dir):
        os.makedirs(current_image_dir) 
    
    # extract frames from video using ffmpeg
    _save_frames(os.path.join(VIDEO_DIR, f.name), current_image_dir)
            
    # use alpr to recognize licence plates from the video frames
    for img_file in glob.glob("%s/*" % current_image_dir):
        print("Detecting plates from frame: ", img_file)
                
        # try on the original image
        best_results = _recognize_image(img_file, top_best=MAX_RESULTS, conf_level=CONF_LEVEL)
        if len(best_results) > 0:
            break
                    
        # preprocess the image and try again
        print("Preprocessing and detecting plates from frame: ", img_file)
        image = cv2.imread(img_file)
        screenCnt = _get_corners(image)
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
            
    return best_results, img_file, metadata

def _add_rdw_data(best_results):
    """
    Loops over the found results and checks if the respective plate numbers exist in the RDW database.
    Where possible, additional data (color and brand of the car) is added to the result.
    If the plate number does not exist, a "hack" is tried: replacing all 'J'-s in the plate number with '4'-s (experiments showed that the alpr tool tends to mix these two characters).
    """
    # check RDW to see if the found plate numbers actually exist
    for car_data in best_results:
        print("Requesting RDW for: ", car_data)
        car_data = _request_rdw(car_data)
            
        # try replacing "J" with "4" (alpr tends to mistake "4" for "J")
        # NOTE: the following solution replaces all "J"-s in the found plate number, but for comprehensiveness, one could try replacing any combination of "J"-s (e.g. replacing only the first occurrence of "J")
        if car_data['exists_in_rdw'] != "Exists" and "J" in car_data['plate_nr']:
            car_data2 = car_data.copy()
            car_data2['plate_nr'] = car_data2['plate_nr'].replace("J", "4")
            car_data2 = _request_rdw(car_data2)
            if car_data2['exists_in_rdw'] == "Exists":
                car_data = car_data2.copy()
                
    return best_results

def _save_video(f, filename, directory):
    """
    The uploaded video file is saved.
    """
    destination_file = open(os.path.join(directory, filename), 'wb+')
    for chunk in f.chunks():
        destination_file.write(chunk)
    destination_file.close()
    
def _save_image(f, filename, directory):
    """
    The uploaded image file is saved.
    """
    fs = FileSystemStorage()
    fs.save(os.path.join(directory, filename), f)
    
def _save_frames(filepath, directory):
    """
    Uses ffmpeg (a command-line tool) to extract and save frames (images) from a video file.
    """
    subprocess.check_output(['ffmpeg','-loglevel', 'panic','-i', filepath, '-vf', 'scale=320:-1', '-r', '10', '-y', os.path.join(directory, "frame_%3d.png")])
       
def _recognize_image(filename, top_best=3, conf_level=80):
    """
    Uses alpr (a command-line tool) to detect plate number from an image.
    If no results are found, returns an empty list.
    If results are found, but even the best result has too low confidence (lower than the specified threshold), returns an empty list.
    If results are found and the best result exceeds the specified confidence threshold, a number of top results (the plate number and the confidence) are returned.
    """
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
    """
    Makes a request to the RDW API to check if the found plate number exists.
    If it does exist, relevant data is added: the color of the car and the brand.
    """
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
    """
    Extracts the uploaded file metadata using exiftool (a command line tool) and determines if the file is "suspicious" or not based on the pre-determined constraints (see the metadata-related variables in the beginning of this module).
    """
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
    
def _get_corners(image):
    """
    Detects a 4-cornered object from the image (hopefully the licence plate) and returns its corners. 
    Code from: http://www.pyimagesearch.com/2014/04/21/building-pokedex-python-finding-game-boy-screen-step-4-6/
    """
    # convert image to grayscale and detect edges
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(gray, 30, 200)
    
    # find contours in the edged image
    (_,cnts, _) = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # sort the contours, so that the ones with larger area come first
    cnts = sorted(cnts, key = cv2.contourArea, reverse = True)
    
    screenCnt = None
    # loop over our contours and search for one with four corners
    for c in cnts:
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        # if our approximated contour has four points, then we assume that we have found our license plate
        if len(approx) == 4:
            screenCnt = approx
            return screenCnt
    
    # no 4-cornered object is found on the image
    return None
        
        
def _process_rect(image, screenCnt):
    """
    Given the corners of the licence plate on the original image, do a perspective transform.
    Helps to make the licence plate "straight" if it was "tilted" on the original image.
    Code from: http://www.pyimagesearch.com/2014/05/05/building-pokedex-python-opencv-perspective-warping-step-5-6/
    """
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
