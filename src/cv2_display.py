from base import BaseComponent
from queue import Queue
import argparse
import redis
from urllib.parse import urlparse
import zerorpc
import gevent
import signal
from core.routine_engine import Events
from core.mini_logics import FramesFromRedis, DisplayCV2, add_logic_to_thread
from core.handlers import tick, tock
import logging
import sys


class CV2VideoDisplay(BaseComponent):

    def __init__(self, output_key, in_key, redis_url, field):
        super().__init__(output_key, in_key)

        self.field = field  # .encode('utf-8')
        self.queue = Queue(maxsize=1)
        t_get_class = add_logic_to_thread(FramesFromRedis)
        t_draw_class = add_logic_to_thread(DisplayCV2)
        self.t_get = t_get_class(self.stop_event, in_key, redis_url, self.queue, self.field, name="get_frames")
        self.t_draw = t_draw_class(self.stop_event, in_key, self.queue, name="draw_frames")

        self.thread_list = [self.t_get, self.t_draw]

        for t in self.thread_list:
            t.add_event_handler(Events.BEFORE_LOGIC, tick)
            t.add_event_handler(Events.AFTER_LOGIC, tock)

        self._start()

    def _start(self):

        for t in self.thread_list:
            t.daemon = True
            t.start()
        return self

    def _inner_stop(self):
        for t in self.thread_list:
            t.join()

    def flip_im(self):
        self.t_get.flip = not self.t_get.flip

    def negative(self):
        self.t_draw.negative = not self.t_draw.negative


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:1')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4244')
    parser.add_argument('--field', help='Image field name', type=str, default='image')
    args = parser.parse_args()

    # Set up Redis connection
    url = urlparse(args.url)
    conn = redis.Redis(host=url.hostname, port=url.port)
    if not conn.ping():
        raise Exception('Redis unavailable')

    zpc = zerorpc.Server(CV2VideoDisplay(None, args.input, url, args.field))
    zpc.bind(f"tcp://0.0.0.0:{args.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
