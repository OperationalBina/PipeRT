# import the necessary packages
from base import BaseComponent
from queue import Queue, Full, Empty
import argparse
from urllib.parse import urlparse
import zerorpc
import gevent
import numpy as np
import signal
from core.routine_engine import RoutineMixin
from core.mini_logics import Frames2Redis, Listen2Stream, add_logic_to_thread
import cv2
from core.routine_engine import Events
from core.handlers import tick, tock
import logging
import sys

import sys
import traceback
import tellopy
import av
import numpy
import time


# def main():
#     drone = tellopy.Tello()
#
#     try:
#         drone.connect()
#         drone.wait_for_connection(60.0)
#
#         container = av.open(drone.get_video_stream())
#         # skip first 300 frames
#         frame_skip = 300
#         while True:
#             for frame in container.decode(video=0):
#                 if 0 < frame_skip:
#                     frame_skip = frame_skip - 1
#                     continue
#                 start_time = time.time()
#                 image = cv2.cvtColor(numpy.array(frame.to_image()), cv2.COLOR_RGB2BGR)
#                 cv2.imshow('Original', image)
#                 cv2.imshow('Canny', cv2.Canny(image, 100, 200))
#                 cv2.waitKey(1)
#                 if frame.time_base < 1.0 / 60:
#                     time_base = 1.0 / 60
#                 else:
#                     time_base = frame.time_base
#                 frame_skip = int((time.time() - start_time) / time_base)
#
#
#     except Exception as ex:
#         exc_type, exc_value, exc_traceback = sys.exc_info()
#         traceback.print_exception(exc_type, exc_value, exc_traceback)
#         print(ex)
#     finally:
#         drone.quit()
#         cv2.destroyAllWindows()
#
#
# if __name__ == '__main__':
#     main()


class DroneVidLogic(RoutineMixin):

    def __init__(self, stop_event, queue, fps=30., *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        # self.stream_address = stream_address
        # self.isFile = not str(stream_address).isdecimal()
        self.stream = None
        self.drone = None
        # self.stream = cv2.VideoCapture(self.stream_address)
        self.queue = queue
        self.frame_skip = 0

    def main_logic(self, *args, **kwargs):
        try:
            packet = next(self.stream)
            if 0 < self.frame_skip:
                self.frame_skip -= 1
                return False

            start_time = time.time()
            frame = cv2.cvtColor(np.array(packet.to_image()), cv2.COLOR_RGB2BGR)
            #                 image = cv2.cvtColor(numpy.array(frame.to_image()), cv2.COLOR_RGB2BGR)
            try:
                self.queue.put(frame)
            except Full:
                try:
                    _ = self.queue.get(block=False)
                except Empty:
                    pass
                finally:
                    self.queue.put(frame, block=False)
            finally:
                if packet.time_base < (1. / 60):
                    time_base = 1. / 60
                else:
                    time_base = packet.time_base
                self.frame_skip = int((time.time() - start_time)/time_base)
                return True
        except Exception as ex:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            print(ex)

    def setup(self, *args, **kwargs):
        self.drone = tellopy.Tello()
        self.drone.connect()
        self.drone.wait_for_connection(60.0)
        self.stream = av.open(self.drone.get_video_stream()).decode(video=0)
        for i in range(300):
            _ = next(self.stream)
        # if not self.isFile:
        #     self.stream.set(cv2.CAP_PROP_FPS, self.fps)
        #     TODO: some cameras don't respect the fps directive
        #     TODO: needs better video resolution
            # self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
            # self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        # else:
        #     self.fps = self.stream.get(cv2.CAP_PROP_FPS)

    def cleanup(self, *args, **kwargs):
        self.drone.quit()


class DroneCapture(BaseComponent):

    def __init__(self, stream_address, out_key, redis_url, fps=30.0, maxlen=100):
        super().__init__(out_key, stream_address)
        # TODO: should queue maxsize be configurable?
        self.queue = Queue(maxsize=1)

        t_stream_class = add_logic_to_thread(DroneVidLogic)
        t_update_class = add_logic_to_thread(Frames2Redis)
        t_stream = t_stream_class(self.stop_event, self.queue, fps, name="capture_frame")
        t_upload = t_update_class(self.stop_event, out_key, redis_url, self.queue, maxlen, name="upload_redis")

        self.thread_list = [t_stream, t_upload]
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
    parser.add_argument('infile', help='Input file (leave empty to use webcam)', nargs='?', type=str, default=None)
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:0')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-w', '--webcam', help='Webcam device number', type=int, default=0)
    parser.add_argument('-v', '--verbose', help='Verbose output', type=bool, default=False)
    parser.add_argument('--count', help='Count of frames to capture', type=int, default=None)
    parser.add_argument('--fmt', help='Frame storage format', type=str, default='.jpg')
    parser.add_argument('--fps', help='Frames per second (webcam)', type=float, default=15.0)
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    args = parser.parse_args()

    # Set up Redis connection
    url = urlparse(args.url)

    # Choose video source
    # if args.infile is None:
    zpc = zerorpc.Server(DroneCapture(stream_address=args.webcam, out_key=args.output, redis_url=url, fps=args.fps,
                                      maxlen=args.maxlen))
    # else:
    #     zpc = zerorpc.Server(DroneVidLogic(stream_address=args.infile, out_key=args.output, redis_url=url, fps=args.fps,
    #                                       maxlen=args.maxlen))
    zpc.bind("tcp://0.0.0.0:4242")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
