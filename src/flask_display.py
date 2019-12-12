import argparse
import redis
from urllib.parse import urlparse
from flask import Flask, Response
from base import BaseComponent
import zerorpc
import gevent
import signal
from core.mini_logics import FramesFromRedis, add_logic_to_thread
from queue import Empty
from multiprocessing import Process, Queue
import cv2


def gen(q):
    while True:
        try:
            frame = q.get(block=False)
            ret, frame = cv2.imencode('.jpg', frame)
            frame = frame.tobytes()
            yield (b'--frame\r\n'
                   b'Pragma-directive: no-cache\r\n'
                   b'Cache-directive: no-cache\r\n'
                   b'Cache-control: no-cache\r\n'
                   b'Pragma: no-cache\r\n'
                   b'Expires: 0\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        except Empty:
            pass


class FlaskVideoDisplay(BaseComponent):

    def __init__(self, output_key, in_key, redis_url, field):
        super().__init__(output_key, in_key)

        self.field = field  # .encode('utf-8')
        self.queue = Queue(maxsize=1)
        t_get_class = add_logic_to_thread(FramesFromRedis)
        self.t_get = t_get_class(self.stop_event, in_key, redis_url, self.queue, self.field, name="get_frames")

        app = Flask(__name__)

        @app.route('/video')
        def video_feed():
            return Response(gen(self.queue),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

        self.server = Process(target=app.run, kwargs={"host": '0.0.0.0'})

        self.routine = [self.t_get, self.server]

        #
        # for t in self.thread_list:
        #     t.add_event_handler(Events.BEFORE_LOGIC, tick)
        #     t.add_event_handler(Events.AFTER_LOGIC, tock)

        self._start()

    def _start(self):

        for t in self.routine:
            t.daemon = True
            t.start()
        return self

    def _inner_stop(self):
        self.server.terminate()
        for t in self.routine:
            t.join()

    def flip_im(self):
        self.t_get.flip = not self.t_get.flip

    def negative(self):
        self.t_get.negative = not self.t_get.negative


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

    zpc = zerorpc.Server(FlaskVideoDisplay(None, args.input, url, args.field))
    zpc.bind(f"tcp://0.0.0.0:{args.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
