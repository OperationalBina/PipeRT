import argparse
from urllib.parse import urlparse
from flask import Flask, Response

from pipert.contrib.metrics_collectors.prometheus_collector import PrometheusCollector
from pipert.contrib.routines import MetaAndFrameFromRedis, VisLogic
from pipert.core.component import BaseComponent
from pipert.contrib.metrics_collectors.splunk_collector import SplunkCollector
from pipert.core.metrics_collector import NullCollector
import queue
from threading import Thread
from pipert.core import QueueHandler
import os


def gen(q: QueueHandler):
    while True:
        encoded_frame = q.non_blocking_get()
        if encoded_frame:
            yield (b'--frame\r\n'
                   b'Pragma-directive: no-cache\r\n'
                   b'Cache-directive: no-cache\r\n'
                   b'Cache-control: no-cache\r\n'
                   b'Pragma: no-cache\r\n'
                   b'Expires: 0\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + encoded_frame + b'\r\n\r\n')


class FlaskVideoDisplay(BaseComponent):

    def __init__(self, in_key_meta, in_key_im, metrics_collector,
                 name="FlaskVideoDisplay"):
        super().__init__(name, metrics_collector)
        self.queue = queue.Queue(maxsize=1)
        self.t_get = MetaAndFrameFromRedis(in_key_meta, in_key_im,
                                           self.queue,
                                           name="get_frames_and_preds",
                                           component_name=self.name,
                                           metrics_collector=self.metrics_collector)
        self.t_get.as_thread()
        self.register_routine(self.t_get)

        self.queue2 = queue.Queue(maxsize=1)
        self.t_vis = VisLogic(self.queue, self.queue2, name="vis_logic",
                              component_name=self.name,
                              metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(self.t_vis)

        app = Flask(__name__)
        app.debug = False

        @app.route('/video')
        def video_feed():
            return Response(gen(QueueHandler(self.queue2)),
                            mimetype='multipart/x-mixed-replace; '
                                     'boundary=frame')

        self.server = Thread(target=app.run, kwargs={"host": '0.0.0.0'})
        self.register_routine(self.server)

    def flip_im(self):
        self.t_get.flip = not self.t_get.flip

    def negative(self):
        self.t_get.negative = not self.t_get.negative


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input_im', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-m', '--input_meta', help='Input stream key name', type=str, default='camera:2')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4246')
    parser.add_argument('--monitoring', help='Name of the monitoring service', type=str, default='prometheus')

    args = parser.parse_args()

    # Set up Redis connection
    # url = urlparse(args.url)
    url = os.environ.get('REDIS_URL')
    url = urlparse(url) if url is not None else urlparse(args.url)

    if args.monitoring == 'prometheus':
        collector = PrometheusCollector(8082)
    elif args.monitoring == 'splunk':
        collector = SplunkCollector()
    else:
        collector = NullCollector()

    zpc = FlaskVideoDisplay(args.input_meta, args.input_im, collector)
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
