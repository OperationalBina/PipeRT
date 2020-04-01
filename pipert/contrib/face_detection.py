import torch

from pipert.core.message import PredictionPayload
from pipert.utils.structures import Instances, Boxes
from pipert.core.component import BaseComponent
from pipert.core.message import Message
from queue import Queue, Empty, Full
import argparse
from urllib.parse import urlparse
import zerorpc
import gevent
import signal
import time
import cv2
from pipert.core.routine import Routine
from pipert.core.mini_logics import Message2Redis, MessageFromRedis
from pipert.core.routine import Events
from pipert.core.handlers import tick, tock


class FaceDetLogic(Routine):

    def __init__(self, in_queue, out_queue, out_frame_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.out_frame_queue = out_frame_queue
        self.face_cas = None

    def main_logic(self, *args, **kwargs):
        try:
            frame_msg = self.in_queue.get(block=False)
            frame = frame_msg.get_payload()
            if frame is not None:
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
                    # print(faces.size(), faces)
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

                pred_msg = Message(new_instances, frame_msg.source_address)
                try:
                    self.out_frame_queue.put(frame_msg, block=False)
                    self.out_queue.put(pred_msg, block=False)
                except Full:
                    return False
                return True
            else:
                time.sleep(0)
                return False

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        casc_path = "pipert/contrib/face_detect/haarcascade_frontalface_default.xml"
        self.face_cas = cv2.CascadeClassifier(casc_path)
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass


class FaceDetComponent(BaseComponent):

    def __init__(self, endpoint, in_key, out_key, out_frame_key, redis_url, maxlen=100, name="FaceDetection", use_memory=False):
        super().__init__(endpoint, name, 8081, use_memory=use_memory)
        # TODO: should queue maxsize be configurable?
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)
        self.out_frame_queue = Queue(maxsize=1)

        r_get = MessageFromRedis(in_key, redis_url, self.in_queue, name="get_from_redis", component_name=self.name).as_thread()
        r_sort = FaceDetLogic(self.in_queue, self.out_queue, self.out_frame_queue, name="face_det_logic", component_name=self.name).as_thread()
        r_upload_meta = Message2Redis(out_key, redis_url, self.out_queue, maxlen, name="upload_meta", component_name=self.name).as_thread()
        r_upload_frame = Message2Redis(out_frame_key, redis_url, self.out_frame_queue, maxlen, name="upload_frame", component_name=self.name).as_thread()

        routines = [r_get, r_sort, r_upload_meta, r_upload_frame]
        for routine in routines:
            # routine.register_events(Events.BEFORE_LOGIC, Events.AFTER_LOGIC)
            # routine.add_event_handler(Events.BEFORE_LOGIC, tick)
            # routine.add_event_handler(Events.AFTER_LOGIC, tock)
            self.register_routine(routine)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:2')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:3')
    parser.add_argument('-of', '--outputFrame', help='Output Frame stream key name', type=str, default='camera:4')
    parser.add_argument('-s', '--shared', help='Shared memory', type=bool, default=False)
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4248')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    # max_age: int = 1, min_hits: int = None, window_size: int = None, percent_seen
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = FaceDetComponent(f"tcp://0.0.0.0:{opt.zpc}", opt.input, opt.output, opt.outputFrame, url, maxlen=opt.maxlen,
                           use_memory=opt.shared)
    print("run")
    zpc.run()
    print("Killed")
