import os
import subprocess
from urllib.parse import urlparse
import redis
import time
import torch

url = urlparse(os.environ.get('REDIS_URL', "redis://vlad_redis:6379"))
conn = redis.Redis(host=url.hostname, port=url.port)
conn.flushall()

display = subprocess.Popen(["python", "-m", "pipert.contrib.flask_display", "-u", "$REDIS_URL", "-i",
                  "camera:0", "-m", "camera:2", "-z", "4246"])

yolov3 = subprocess.Popen(["python", "-m", "pipert.contrib.yolov3", "-u", "$REDIS_URL", "-i",
                  "camera:0", "-o", "camera:2", "-z", "4243"])

time.sleep(8)

vid_cap = subprocess.Popen(["python", "-m", "pipert.contrib.vid_capture", "-u", "$REDIS_URL", "-i",
                  "pipert/test.mp4"])

input("Press enter to shut down the pipeline")

vid_cap.kill()
yolov3.kill()
display.kill()

time.sleep(1)

conn.flushall()

