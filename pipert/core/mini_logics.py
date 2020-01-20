from pipert.core.routine import Routine
import time
from queue import Empty, Full
import redis
from imutils import resize
from pipert.utils.image_enc_dec import metadata_decode, metadata_encode
import cv2
import numpy as np
import io
from PIL import Image


class Listen2Stream(Routine):

    def __init__(self, stream_address, queue, fps=30., *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_address = stream_address
        self.isFile = str(stream_address).endswith("mp4")
        self.stream = None
        # self.stream = cv2.VideoCapture(self.stream_address)
        self.queue = queue
        self.fps = fps
        self.updatedConfig = {}

    def changeSourceStream(self):
        if self.stream_address == self.updatedConfig['stream_address']:
            return

        self.stream_address = self.updatedConfig['stream_address']
        self.fps = self.updatedConfig['FPS']
        self.isFile = str(self.stream_address).endswith("mp4")
        self.setup()

    def main_logic(self, *args, **kwargs):
        if self.updatedConfig:
            self.changeSourceStream()
            self.updatedConfig = {}

        start = time.time()
        grabbed, frame = self.stream.read()
        if grabbed:
            frame = resize(frame, 640, 480)
            if not self.isFile:
                frame = cv2.flip(frame, 1)
            try:
                self.queue.get(block=False)
            except Empty:
                pass
            finally:
                self.queue.put(frame)
                if self.isFile:
                    wait = time.time() - start
                    time.sleep(max(1 / self.fps - wait, 0))
                # self.queue.put(frame, block=False)
                time.sleep(0)
                return True
            # except Full:
            #     try:
            #         self.queue.get(block=False)
            #     except Empty:
            #         pass
            #     finally:
            #         self.queue.put(frame, block=False)
            #         time.sleep(0)
            #         return True
                # time.sleep(0)
                # return False

    def setup(self, *args, **kwargs):
        self.stream = cv2.VideoCapture(self.stream_address)
        if self.isFile:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        #     self.stream.set(cv2.CAP_PROP_FPS, self.fps)
        #     # TODO: some cameras don't respect the fps directive
        #     # TODO: needs better video resolution
        #     # self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        #     # self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        # else:
        #     self.fps = self.stream.get(cv2.CAP_PROP_FPS)

    def cleanup(self, *args, **kwargs):
        self.stream.release()
        del self.stream


# TODO: add Error handling to connection
class Frames2Redis(Routine):

    def __init__(self, out_key, url, queue, maxlen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = out_key
        self.url = url
        self.queue = queue
        self.maxlen = maxlen
        # self.maxlen = 1

        self.conn = None

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.queue.get(block=False)
            _, data = cv2.imencode(".jpg", frame)
            msg = {
                'count': self.state.count,
                'image': data.tobytes()
            }
            _ = self.conn.xadd(self.out_key, msg, maxlen=self.maxlen)
            time.sleep(0)
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


class FramesFromRedis(Routine):

    def __init__(self, in_key, url, queue, field, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class MetadataFromRedis(Routine):

    def __init__(self, in_key, url, queue, field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key = in_key
        self.url = url
        self.queue = queue
        self.field = field.encode('utf-8')
        self.conn = None
        self.flip = False
        self.negative = False

    def main_logic(self, *args, **kwargs):
        # TODO - refactor to use xread instead of xrevrange
        msg = self.conn.xrevrange(self.in_key, count=1)  # Latest frame
        # cmsg = self.conn.xread({self.in_key: "$"}, None, 1)
        if msg:
            data = metadata_decode(msg[0][1][self.field])
            try:
                self.queue.put(data, block=False)
                return True
            except Full:
                try:
                    self.queue.get(block=False)
                except Empty:
                    pass
                finally:
                    self.queue.put(data, block=False)
                    return True
        else:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.conn = redis.Redis(host=self.url.hostname, port=self.url.port)
        if not self.conn.ping():
            raise Exception('Redis unavailable')

    def cleanup(self, *args, **kwargs):
        self.conn.close()


class Metadata2Redis(Routine):

    def __init__(self, out_key, url, queue, field, maxlen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = out_key
        self.url = url
        self.queue = queue
        self.maxlen = maxlen
        self.field = field

        self.conn = None

    def main_logic(self, *args, **kwargs):
        try:
            data = self.queue.get(block=False)
            data_msg = metadata_encode(data)
            msg = {
                "count": self.state.count,
                f"{self.field}": data_msg
            }
            _ = self.conn.xadd(self.out_key, msg, maxlen=self.maxlen)
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


class DisplayCV2(Routine):
    def __init__(self, in_key, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class DisplayFlask(Routine):
    def __init__(self, in_key, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
