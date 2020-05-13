import time
from queue import Empty

import cv2

from imutils import resize

from pipert.core import QueueHandler
from pipert.core.message import Message
from pipert.core.routine import Routine, RoutineTypes


class ListenToStream(Routine):
    routine_type = RoutineTypes.INPUT

    def __init__(self, stream_address, queue, fps=30., use_memory=False,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_address = stream_address
        self.is_file = str(stream_address).endswith("mp4")
        self.stream = None
        self.q_handler = QueueHandler(queue)
        self.updated_config = {}
        if self.is_file:
            self.sma = SimpleMovingAverage(value=0.1, count=19)
            self.ts = time.time()
        self.fps = fps

    def begin_capture(self):
        self.stream = cv2.VideoCapture(self.stream_address)
        if self.is_file:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        _, _ = self.grab_frame()
        self.logger.info("Starting video capture on %s", self.stream_address)

    def change_stream(self):
        if self.stream_address == self.updated_config['stream_address']:
            return
        self.stream_address = self.updated_config['stream_address']
        self.fps = self.updated_config['FPS']
        self.is_file = str(self.stream_address).endswith("mp4")
        self.logger.info("Changing source stream address to %s",
                         self.updated_config['stream_address'])
        self.begin_capture()

    def grab_frame(self):
        grabbed, frame = self.stream.read()
        msg = Message(frame, self.stream_address)
        msg.record_entry(self.component_name, self.logger)
        return grabbed, msg

    def main_logic(self, *args, **kwargs):
        if self.updated_config:
            self.change_stream()
            self.updated_config = {}

        grabbed, frame = self.stream.read()
        if grabbed:
            msg = Message(frame, self.stream_address)
            msg.record_entry(self.component_name, self.logger)

            frame = resize(frame, 640, 480)
            # if the stream is from a webcam, flip the frame
            if self.stream_address == 0:
                frame = cv2.flip(frame, 1)
            msg.update_payload(frame)

            success = self.q_handler.deque_non_blocking_put(msg)
            if self.is_file:
                delta = time.time() - self.ts
                self.sma.add(delta)
                time.sleep(max(0, (1.0 - self.sma.current * self.fps) / self.fps))
                self.ts = time.time()
            return success

        else:
            self.cleanup()
            self.begin_capture()

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
        return self.q_handler.q == queue


class SimpleMovingAverage(object):
    ''' Simple moving average '''
    def __init__(self, value=0.0, count=7):
        self.count = int(count)
        self.current = float(value)
        self.samples = [self.current] * self.count

    def __str__(self):
        return str(round(self.current, 3))

    def add(self, value):
        v = float(value)
        self.samples.insert(0, v)
        o = self.samples.pop()
        self.current = self.current + (v-o)/self.count
