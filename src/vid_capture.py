# import the necessary packages
from base import BaseComponent
from queue import Queue
import argparse
from urllib.parse import urlparse
import zerorpc
import gevent
import signal
from core.mini_logics import Frames2Redis, Listen2Stream, add_logic_to_thread
from core.routine_engine import Events
from core.handlers import tick, tock
import logging
import sys


class VideoCapture(BaseComponent):

    def __init__(self, stream_address, out_key, redis_url, fps=30.0, maxlen=10):
        super().__init__(out_key, stream_address)
        # TODO: should queue maxsize be configurable?
        self.queue = Queue(maxsize=1)

        t_stream_class = add_logic_to_thread(Listen2Stream)
        t_update_class = add_logic_to_thread(Frames2Redis)
        t_stream = t_stream_class(self.stop_event, stream_address, self.queue, fps, name="capture_frame")
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
    if args.infile is None:
        zpc = zerorpc.Server(VideoCapture(stream_address=args.webcam, out_key=args.output, redis_url=url, fps=args.fps,
                                          maxlen=args.maxlen))
    else:
        zpc = zerorpc.Server(VideoCapture(stream_address=args.infile, out_key=args.output, redis_url=url, fps=args.fps,
                                          maxlen=args.maxlen))
    zpc.bind("tcp://0.0.0.0:4242")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
