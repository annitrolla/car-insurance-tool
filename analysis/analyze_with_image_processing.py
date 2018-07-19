import os, sys
import glob
import json
import cv2
import subprocess
import re
import requests
import cv2
import numpy as np

def save_frames(filepath, directory):
    subprocess.check_output(['ffmpeg','-loglevel','panic','-i', filepath, '-vf', 'scale=320:-1', '-r', '10', '-y', os.path.join(directory, "frame_%3d.png")])
       
def recognize_image(filename, top_best=10):
    results = str(subprocess.check_output(['alpr', '-c', 'eu', filename]))
    results = results[1:].strip("'").split("\\n")[1:]
    best_results = []
    if len(results) > 1:
        m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[0].strip())
        plate_nr, confidence = m.group(1), float(m.group(2))
        for i in range(min(top_best, len(results))):
            m = re.match(r"- (\w*)\\t confidence: (\d*.\d*)", results[i].strip())
            if m:
                best_results.append({"plate_nr": m.group(1), "confidence": float(m.group(2))})
    return best_results
    
def request_rdw(car_data):
    if car_data['plate_nr'] in rdw_data_dict:
        car_data["exists_in_rdw"] = rdw_data_dict[car_data['plate_nr']]["exists_in_rdw"]
        car_data["color"] = rdw_data_dict[car_data['plate_nr']]["color"]
        car_data["brand"] = rdw_data_dict[car_data['plate_nr']]["brand"]
    else:
        url = "http://api.datamarket.azure.com/opendata.rdw/VRTG.Open.Data/v1/KENT_VRTG_O_DAT(\'%s\')?$format=json" % car_data['plate_nr']
        r = requests.get(url).json()
        rdw_data_dict[car_data['plate_nr']] = {}
        if "error" in r:
            car_data["exists_in_rdw"] = "Does not exist"
            car_data["color"] = "-"
            car_data["brand"] = "-"

            rdw_data_dict[car_data['plate_nr']]["exists_in_rdw"] = "Does not exist"
            rdw_data_dict[car_data['plate_nr']]["color"] = "-"
            rdw_data_dict[car_data['plate_nr']]["brand"] = "-"
        else:
            car_data["exists_in_rdw"] = "Exists"
            car_data["color"] = r["d"]["Eerstekleur"]
            car_data["brand"] = r["d"]["Merk"]

            rdw_data_dict[car_data['plate_nr']]["exists_in_rdw"] = "Exists"
            rdw_data_dict[car_data['plate_nr']]["color"] = r["d"]["Eerstekleur"]
            rdw_data_dict[car_data['plate_nr']]["brand"] = r["d"]["Merk"]
    return car_data

def get_edges(image):
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
        
        
def process_rect(screenCnt):
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
    
    

rdw_data_dict = {}

results_file = 'results_image_processing5.csv'
video_dir = 'Movies2'
image_dir = 'analyze_images'
if not os.path.exists(image_dir):
    os.makedirs(image_dir)
    
with open(results_file, 'w') as fout:
    header = ['video_file', 'is_valid_file', 'frame', 'plate_nr', 'confidence', 'exists_in_rdw', 'car_color', 'car_brand', 'prediction_rank', 'processed']
    fout.write(",".join(header))
    fout.write("\n")
    
    for video_file in glob.glob("%s/*" % video_dir):
        print(video_file)
        
        filename = os.path.basename(video_file)
        file_basename, file_extension = os.path.splitext(filename)
        
        current_image_dir = os.path.join(image_dir, file_basename)
        if not os.path.exists(current_image_dir):
            os.makedirs(current_image_dir)
        try:
            # file is an image file
            if file_extension in ['jpg', 'jpeg', 'png']:
                
                # convert to png if necessary (alpr works better with png than with jpg)
                if file_extension != "png":
                    subprocess.check_output(['mogrify', '-format', 'png', '-g1', video_file])
                filename = video_file.replace(file_extension, "png")
                subprocess.check_output(['cp', filename, current_image_dir])

            # file is a video file
            else:
                # extract frames from video using ffmpeg
                save_frames(video_file, current_image_dir)

            results_found = False
            confident_results_found = False
            for img_file in glob.glob("%s/*" % current_image_dir):
                # try alpr without processing
                results = recognize_image(img_file)
                for i, result in enumerate(results):
                    if len(result['plate_nr']) == 6:
                        results_found = True
                        result = request_rdw(result)
                        fout.write(",".join([file_basename, "True",
                                        os.path.basename(img_file),
                                        result['plate_nr'], str(result['confidence']),
                                        result['exists_in_rdw'], result['color'],
                                        result['brand'], str(i), "False"]))
                        fout.write("\n")
                        
                        # try replacing "J" with "4"
                        if result['exists_in_rdw'] != "Exists" and "J" in result['plate_nr']:
                            result['plate_nr'] = result['plate_nr'].replace("J", "4")
                            result = request_rdw(result)
                            if result['exists_in_rdw'] == "Exists":
                                fout.write(",".join([file_basename, "True",
                                        os.path.basename(img_file),
                                        result['plate_nr'], str(result['confidence']),
                                        result['exists_in_rdw'], result['color'],
                                        result['brand'], str(i)+"a", "False"]))
                                fout.write("\n")
                        
                        if result['exists_in_rdw'] == "Exists" and result['confidence'] > 80:
                            confident_results_found = True
                
                # process image
                image = cv2.imread(img_file)
                screenCnt = get_edges(image)
                if screenCnt is None:
                    print("No 4-cornered contour found")
                else:
                    warp = process_rect(screenCnt)
                    warp_padded = cv2.copyMakeBorder(warp, 50, 50, 50, 50, cv2.BORDER_CONSTANT)
                    cv2.imwrite('warped.png',warp_padded)

                    # alpr
                    results = recognize_image('warped.png')
                    for i, result in enumerate(results):
                        if len(result['plate_nr']) == 6:
                            results_found = True
                            result = request_rdw(result)
                            fout.write(",".join([os.path.basename(video_file)[:-4], "True",
                                                os.path.basename(img_file),
                                                result['plate_nr'], str(result['confidence']),
                                                result['exists_in_rdw'], result['color'],
                                                result['brand'], str(i), "True"]))
                            fout.write("\n")
                            
                            # try replacing "J" with "4"
                            if result['exists_in_rdw'] != "Exists" and "J" in result['plate_nr']:
                                result['plate_nr'] = result['plate_nr'].replace("J", "4")
                                result = request_rdw(result)
                                if result['exists_in_rdw'] == "Exists":
                                    fout.write(",".join([file_basename, "True",
                                            os.path.basename(img_file),
                                            result['plate_nr'], str(result['confidence']),
                                            result['exists_in_rdw'], result['color'],
                                            result['brand'], str(i)+"a", "True"]))
                                    fout.write("\n")
                            
                            if result['exists_in_rdw'] == "Exists" and result['confidence'] > 80:
                                confident_results_found = True
                if confident_results_found:
                    break
            if not results_found:
                fout.write(",".join([os.path.basename(video_file)[:-4], "True",
                                    'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'
                                    ]))
            fout.write("\n") 
        except subprocess.CalledProcessError:
            fout.write(",".join([os.path.basename(video_file)[:-4], "False",
                                    'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'
                                    ]))
            fout.write("\n")
            
