import time
from queue import Empty
import cv2

from imutils import resize
from pipert.core.message import Message
from pipert.core.routine import Routine, RoutineTypes


class ListenToStream(Routine):
    routine_type = RoutineTypes.INPUT

    def __init__(self, stream_address, out_queue, fps=30., *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.stream_address = int(stream_address)
        except ValueError:
            self.stream_address = stream_address
        self.isFile = str(stream_address).endswith("mp4")
        self.stream = None
        # self.stream = cv2.VideoCapture(self.stream_address)
        self.out_queue = out_queue
        self.fps = fps
        self.updated_config = {}

    def begin_capture(self):
        self.stream = cv2.VideoCapture(self.stream_address)
        if self.isFile:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.logger.info("Starting video capture on %s", self.stream_address)

    def change_stream(self):
        if self.stream_address == self.updated_config['stream_address']:
            return
        self.stream_address = self.updated_config['stream_address']
        self.fps = self.updated_config['FPS']
        self.isFile = str(self.stream_address).endswith("mp4")
        self.logger.info("Changing source stream address to %s",
                         self.updated_config['stream_address'])
        self.begin_capture()

    def grab_frame(self):
        if self.stream.isOpened():
            grabbed, frame = self.stream.read()
            if grabbed:
                msg = Message(frame, self.stream_address)
                msg.id = f"{self.stream_address}_{self.counter}"
                self.counter += 1
                msg.record_entry(self.component_name, self.logger)
            else:
                self.logger.info("Failed to capture frame")
                msg = None
            return grabbed, msg
        else:
            self.logger.info("Failed to open stream")
            self.logger.info("Retrying...")
            self.begin_capture()
            return False, None

    def main_logic(self, *args, **kwargs):
        if self.updated_config:
            self.change_stream()
            self.updated_config = {}

        grabbed, msg = self.grab_frame()
        time.sleep(0.03)
        if grabbed:
            try:
                self.out_queue.get(block=False)
            except Empty:
                pass
            finally:
                self.out_queue.put(msg)
                time.sleep(0)
                return True

    def setup(self, *args, **kwargs):
        self.begin_capture()

    def cleanup(self, *args, **kwargs):
        self.stream.release()
        del self.stream

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "stream_address": "String",
            "out_queue": "QueueOut",
            "fps": "Integer"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.out_queue == queue
