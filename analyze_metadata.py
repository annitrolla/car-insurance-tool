import os, sys
import glob
import json
import cv2
import subprocess
import re

def video_metadata(filename):
    metadata = subprocess.check_output(['exiftool', '-a', '-u', '-g1', filename])
    parts = str(metadata).strip().split('\\n')
    d = {part.split(" : ")[0].strip(): part.split(" : ")[1].strip() for part in parts if len(part.split(" : ")) > 1}
    return d


results_file = 'loxodon_metadata_results.csv'
video_dir = 'Movies'
files = glob.glob("%s/*" % video_dir)
    
all_fields = set()
for video_file in files:
    d = video_metadata(video_file)
    all_fields.update(d.keys())
all_fields = list(all_fields)
    
with open(results_file, 'w') as fout:
    header = "video_file;%s" % (";".join(all_fields))
    fout.write(header)
    fout.write("\n")
    for video_file in files:
        print(video_file)
        d = video_metadata(video_file)
        vals = [d[k] if k in d else "NA" for k in all_fields]
        line = "%s;%s" % (os.path.basename(video_file)[:-4], ";".join(vals))
        fout.write(line)
        fout.write("\n")
        