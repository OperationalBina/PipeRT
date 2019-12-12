from core.routine_engine import ExtendedProcess, ExtendedThread, RoutineMixin
import time
import cv2
from queue import Empty, Full
import redis
import io
import numpy as np
from PIL import Image
# from imutils import resize


class Listen2Stream(RoutineMixin):

    def __init__(self, stop_event, stream_address, queue, fps=30., *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.stream_address = stream_address
        self.isFile = not str(stream_address).isdecimal()
        self.stream = None
        # self.stream = cv2.VideoCapture(self.stream_address)
        self.queue = queue
        self.fps = fps

    def main_logic(self, *args, **kwargs):
        grabbed, frame = self.stream.read()
        if grabbed:
            # frame = resize(frame, 400)
            if not self.isFile:
                frame = cv2.flip(frame, 1)
            try:
                self.queue.put(frame)
                return True
            except Full:
                time.sleep(0)
                return False

    def setup(self, *args, **kwargs):
        self.stream = cv2.VideoCapture(self.stream_address)
        if not self.isFile:
            self.stream.set(cv2.CAP_PROP_FPS, self.fps)
            # TODO: some cameras don't respect the fps directive
            # TODO: needs better video resolution
            # self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
            # self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        else:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)

    def cleanup(self, *args, **kwargs):
        self.stream.release()


# TODO: add Error handling to connection
class Frames2Redis(RoutineMixin):

    def __init__(self, stop_event, out_key, url, queue, maxlen, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.out_key = out_key
        self.url = url
        self.queue = queue
        # self.maxlen = maxlen
        self.maxlen = 1

        self.conn = None

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.queue.get(block=False)
            _, data = cv2.imencode(".jpg", frame)
            msg = {
                'count': self.state.count,
                'image': data.tobytes()
            }
            _id = self.conn.xadd(self.out_key, msg, maxlen=self.maxlen)
            return True
        except Empty:
            time.sleep(0)  # yield the control of the thread
            return False

    def setup(self, *args, **kwargs):
        self.conn = redis.Redis(host=self.url.hostname, port=self.url.port)
        if not self.conn.ping():
            raise Exception('Redis unavailable')

    def cleanup(self, *args, **kwargs):
        self.conn.close()


class FramesFromRedis(RoutineMixin):

    def __init__(self, stop_event, in_key, url, queue, field, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_key = in_key
        self.url = url
        self.queue = queue
        self.field = field.encode('utf-8')
        self.conn = None
        self.flip = False
        self.negative = False

    def main_logic(self, *args, **kwargs):
        # TODO - refactor to use xread instead of xrevrange
        cmsg = self.conn.xrevrange(self.in_key, count=1)  # Latest frame
        # cmsg = self.conn.xread({self.in_key: "$"}, None, 1)
        if cmsg:
            # data = io.BytesIO(cmsg[0][1][0][1][self.field])
            data = io.BytesIO(cmsg[0][1][self.field])
            img = Image.open(data)
            arr = np.array(img)
            if len(arr.shape) == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
            if self.flip:
                arr = cv2.flip(arr, 1)
            if self.negative:
                arr = 255 - arr

            # last_id = cmsg[0][0].decode('utf-8')
            # label = f'{self.in_key}:{last_id}'
            # cv2.putText(arr, label, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1, cv2.LINE_AA)
            try:
                self.queue.put(arr, block=False)
                return True
            except Full:
                try:
                    self.queue.get(block=False)
                except Empty:
                    pass
                return False

        else:
            time.sleep(0)

    def setup(self, *args, **kwargs):
        self.conn = redis.Redis(host=self.url.hostname, port=self.url.port)
        if not self.conn.ping():
            raise Exception('Redis unavailable')

    def cleanup(self, *args, **kwargs):
        self.conn.close()


class DisplayCV2(RoutineMixin):
    def __init__(self, stop_event, in_key, queue, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_key = in_key
        self.queue = queue
        self.negative = False

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.queue.get(block=False)
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


class DisplayFlask(RoutineMixin):
    def __init__(self, stop_event, in_key, queue, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_key = in_key
        self.queue = queue
        self.negative = False

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.queue.get(block=False)
            if self.negative:
                frame = 255 - frame
            cv2.imshow('Display', frame)
            cv2.waitKey(1)
            return True
        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        cv2.destroyAllWindows()


def add_logic_to_thread(logic):

    class ThreadWithLogic(logic, ExtendedThread):
        def __init__(self, stop_event, *args, **kwargs):
            logic.__init__(self, stop_event, *args, **kwargs)
            ExtendedThread.__init__(self, stop_event, *args, **kwargs)

    return ThreadWithLogic


def add_logic_to_process(logic):

    class ProcessWithLogic(logic, ExtendedProcess):
        def __init__(self, stop_event, *args, **kwargs):
            logic.__init__(self, stop_event, *args, **kwargs)
            ExtendedProcess.__init__(self, stop_event, *args, **kwargs)

    return ProcessWithLogic
