import torch
from detectron2.structures import Instances, Boxes
import numpy as np
from src.base import BaseComponent
from queue import Queue, Empty
import argparse
from urllib.parse import urlparse
import zerorpc
import gevent
import signal
import time
import cv2
from src.core.routine_engine import RoutineMixin
from src.core.mini_logics import add_logic_to_thread, Metadata2Redis, FramesFromRedis


class FaceDetLogic(RoutineMixin):

    def __init__(self, stop_event, in_queue, out_queue, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.face_cas = None

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.in_queue.get(block=False)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = self.face_cas.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(20, 20)
            )
            if len(faces):
                faces = torch.from_numpy(faces)
                faces[:, 2:] += faces[:, :2]
                print(faces.size(), faces)
                new_instances = Instances(frame.shape[:2])
                new_instances.set("pred_boxes", Boxes(faces))
                new_instances.set("pred_classes", torch.zeros(faces.size(0)).int())
            else:
                new_instances = Instances(frame.shape[:2])
                new_instances.set("pred_classes", [])

            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            self.out_queue.put(new_instances)
            return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        casc_path = "/home/itamar/PycharmProjects/PipeRT/contrib/face_detect/haarcascade_frontalface_default.xml"
        self.face_cas = cv2.CascadeClassifier(casc_path)
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass


class FaceDetComponent(BaseComponent):

    def __init__(self, in_key, out_key, redis_url, field, maxlen=100, *args, **kwargs):
        super().__init__(out_key, in_key)
        # TODO: should queue maxsize be configurable?
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)
        t_get_class = add_logic_to_thread(FramesFromRedis)
        t_sort_class = add_logic_to_thread(FaceDetLogic)
        t_upload_meta_class = add_logic_to_thread(Metadata2Redis)

        t_get = t_get_class(self.stop_event, in_key, redis_url, self.in_queue, field)
        t_sort = t_sort_class(self.stop_event, self.in_queue, self.out_queue, *args, **kwargs)
        t_upload_meta = t_upload_meta_class(self.stop_event, out_key, redis_url, self.out_queue, "instances", maxlen,
                                            name="upload_redis")

        self.thread_list = [t_get, t_sort, t_upload_meta]
        # for t in self.thread_list:
        #     t.add_event_handler(Events.BEFORE_LOGIC, tick)
        #     t.add_event_handler(Events.AFTER_LOGIC, tock)

        self._start()

    def _start(self):
        # start the thread to read frames from the video stream and upload to
        # redis

        for t in self.thread_list:
            t.daemon = True
            t.start()
        return self

    def _inner_stop(self):
        for t in self.thread_list:
            t.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:2')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:3')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4248')
    parser.add_argument('--field', help='Image field name', type=str, default='image')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    # max_age: int = 1, min_hits: int = None, window_size: int = None, percent_seen
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = zerorpc.Server(FaceDetComponent(opt.input, opt.output, url, opt.field, opt.maxlen))
    zpc.bind(f"tcp://0.0.0.0:{opt.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
