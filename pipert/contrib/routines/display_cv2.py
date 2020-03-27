import time
from queue import Empty
import cv2
from pipert.core.routine import Routine, RoutineTypes


class DisplayCv2(Routine):
    routine_type = RoutineTypes.OUTPUT

    def __init__(self, frame_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame_queue = frame_queue
        self.negative = False

    def main_logic(self, *args, **kwargs):
        try:
            msg = self.frame_queue.get(block=False)
            frame = msg.get_payload()
            if self.negative:
                frame = 255 - frame
            cv2.imshow(self.name, frame)
            cv2.waitKey(1)
        except Empty:
            time.sleep(0)

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        cv2.destroyAllWindows()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "frame_queue": "Queue"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.frame_queue == queue
