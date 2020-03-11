import time
from queue import Empty, Queue
import cv2
from pipert.core.routine import Routine
import random


class DisplayCv2(Routine):
    def __init__(self, frame_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = frame_queue
        self.negative = False

    def main_logic(self, *args, **kwargs):
        try:
            msg = self.queue.get(block=False)
            frame = msg.get_payload()
            if self.negative:
                frame = 255 - frame
            self.name = str(random.randint(1, 10000))
            print(self.name, "1")
            print(frame)
            cv2.imshow(self.name, frame)
            cv2.startWindowThread()
            print(self.name, "2")
            cv2.waitKey(1)
            print(self.name, "3")
        except Empty:
            time.sleep(0)
        except Exception as e:
            print(e.__traceback__)

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        cv2.destroyWindow(self.name)
        # cv2.destroyAllWindows()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "frame_queue": "Queue"
        })
        return dicts
