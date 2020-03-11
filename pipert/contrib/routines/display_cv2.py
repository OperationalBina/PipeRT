import time
from queue import Empty
import cv2
from pipert.core.routine import Routine


class DisplayCV2(Routine):
    def __init__(self, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue
        self.negative = False

    def main_logic(self, *args, **kwargs):
        try:
            msg = self.queue.get(block=False)
            frame = msg.get_payload()
            if self.negative:
                frame = 255 - frame
            cv2.imshow('Display', frame)
            cv2.waitKey(1)
        except Empty:
            time.sleep(0)

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        cv2.destroyAllWindows()
