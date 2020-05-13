import os
import subprocess
from urllib.parse import urlparse
import redis
import time

os.environ['REDIS_URL'] = "redis://vlad_redis:6379"
url = urlparse(os.environ.get('REDIS_URL'))
conn = redis.Redis(host=url.hostname, port=url.port)
time.sleep(1)
conn.flushall()

batch = 1

display = subprocess.Popen(["python", "-m", "pipert.contrib.flask_display", "-u",
                            "$REDIS_URL", "-i", "camera:0", "-m", "camera:y0", "-z", "4246"])

yolov3 = subprocess.Popen(["python", "-m", "pipert.contrib.yolov3", "-u", "$REDIS_URL", "-b", str(batch), "-z", "4243"])

time.sleep(8)

vid_caps = [subprocess.Popen(["python", "-m", "pipert.contrib.vid_capture", "-u", "$REDIS_URL", "-i",
                  f"pipert/test.mp4", "-o", f"camera:{i}"]) for i in range(batch)]

input("Press enter to shut down the pipeline\n")

try:
    [_.terminate() for _ in vid_caps]
    yolov3.terminate()
    display.terminate()
    time.sleep(1)
except:
    pass
finally:
    try:
        [_.kill() for _ in vid_caps]
        yolov3.kill()
        display.kill()
        time.sleep(1)
    except:
        pass
    finally:
        conn.flushall()

