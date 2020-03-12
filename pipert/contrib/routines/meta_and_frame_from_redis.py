from urllib.parse import urlparse

from pipert.core.routine import Routine
from queue import Empty
import cv2
from pipert.core.message import message_decode
from pipert.core.message_handlers import RedisHandler
import time


class MetaAndFrameFromRedis(Routine):

    def __init__(self, redis_read_meta_key, redis_read_image_key, url, image_meta_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key_meta = redis_read_meta_key
        self.in_key_im = redis_read_image_key
        self.url = urlparse(url)
        self.queue = image_meta_queue
        self.msg_handler = None
        self.flip = False
        self.negative = False

    def receive_msg(self, in_key):
        encoded_msg = self.msg_handler.read_most_recent_msg(in_key)
        if not encoded_msg:
            return None
        msg = message_decode(encoded_msg)
        msg.record_entry(self.component_name, self.logger)
        return msg

    def main_logic(self, *args, **kwargs):
        pred_msg = self.receive_msg(self.in_key_meta)
        frame_msg = self.receive_msg(self.in_key_im)
        if frame_msg:
            arr = frame_msg.get_payload()

            if self.flip:
                arr = cv2.flip(arr, 1)

            if self.negative:
                arr = 255 - arr

            try:
                self.queue.get(block=False)
            except Empty:
                pass
            frame_msg.update_payload(arr)
            self.queue.put((frame_msg, pred_msg))
            return True

        else:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url)

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()
