import os, sys
import glob
import json
import cv2
import subprocess
import re
import requests

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


results_file = 'loxodon_results.csv'
video_dir = '/Users/annaleontjeva/Projects/Loxodon/Movies'
image_dir = 'analyze_images'
if not os.path.exists(image_dir):
    os.makedirs(image_dir)
    
with open(results_file, 'w') as fout:
    header = ['video_file', 'is_valid_file', 'frame', 'plate_nr', 'confidence', 'exists_in_rdw', 'car_color', 'car_brand', 'prediction_rank']
    fout.write(",".join(header))
    fout.write("\n")
    for video_file in glob.glob("%s/*" % video_dir):
        print(video_file)
        current_image_dir = os.path.join(image_dir, os.path.basename(video_file)[:-4])
        if not os.path.exists(current_image_dir):
            os.makedirs(current_image_dir)
        try:
            save_frames(video_file, current_image_dir)
            results_found = False
            for img_file in glob.glob("%s/*" % current_image_dir):
                results = recognize_image(img_file)
                if len(results) > 0:
                    results_found = True
                for i, result in enumerate(results):
                    result = request_rdw(result)
                    fout.write(",".join([os.path.basename(video_file)[:-4], "True",
                                        os.path.basename(img_file),
                                        result['plate_nr'], str(result['confidence']),
                                        result['exists_in_rdw'], result['color'],
                                        result['brand'], str(i)]))
                    fout.write("\n")
            if not results_found:
                fout.write(",".join([os.path.basename(video_file)[:-4], "True",
                                    'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'
                                    ]))
            fout.write("\n") 
        except subprocess.CalledProcessError:
            fout.write(",".join([os.path.basename(video_file)[:-4], "False",
                                    'NA', 'NA', 'NA', 'NA', 'NA', 'NA', 'NA'
                                    ]))
            fout.write("\n")
            
        

        