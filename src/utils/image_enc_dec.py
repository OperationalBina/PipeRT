import cv2
import io
from PIL import Image
import numpy as np
import dill


def image_encode(image, im_format=".jpg"):
    return cv2.imencode(im_format, image)


def image_decode(msg):
    data = io.BytesIO(msg[0][1]["image".encode("utf-8")])
    img = Image.open(data)
    return np.array(img)


def metadata_decode(msg):
    return dill.loads(msg)


def metadata_encode(data):
    return dill.dumps(data)
