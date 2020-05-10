from pipert import BaseComponent
from queue import Queue
import argparse
from urllib.parse import urlparse
import os

from pipert.contrib.metrics_collectors.prometheus_collector import PrometheusCollector
from pipert.contrib.routines import ListenToStream, MessageToRedis
from pipert.core.metrics_collector import NullCollector
from pipert.contrib.metrics_collectors.splunk_collector import SplunkCollector


class VideoCapture(BaseComponent):

    def __init__(self, stream_address, out_key, metrics_collector, use_memory=False, fps=30.0,
                 maxlen=10, name="VideoCapture"):
        super().__init__(name, metrics_collector, use_memory=use_memory)
        # TODO: should queue maxsize be configurable?
        self.queue = Queue(maxsize=1)

        t_stream = ListenToStream(stream_address, self.queue, fps, name="capture_frame", component_name=self.name,
                                  metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_stream)

        t_upload = MessageToRedis(out_key, self.queue, maxlen, name="upload_redis", component_name=self.name,
                                  metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_upload)

    def change_stream(self, stream_address, fps=30.0):
        self._routines["capture_frame"].updated_config = {"stream_address": stream_address, "FPS": fps}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', help='Input file (leave empty to use webcam)', nargs='?', type=str,
                        default=None)
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:0')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-w', '--webcam', help='Webcam device number', type=int, default=0)
    parser.add_argument('-v', '--verbose', help='Verbose output', type=bool, default=False)
    parser.add_argument('--monitoring', help='Name of the monitoring service', type=str, default='prometheus')
    parser.add_argument('-s', '--shared', help='Shared memory', type=bool, default=False)
    parser.add_argument('--count', help='Count of frames to capture', type=int, default=None)
    parser.add_argument('--fmt', help='Frame storage format', type=str, default='.jpg')
    parser.add_argument('--fps', help='Frames per second (webcam)', type=float, default=15.0)
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    opts = parser.parse_args()

    # Set up Redis connection
    url = os.environ.get('REDIS_URL')
    url = urlparse(url) if url is not None else urlparse(opts.url)

    if opts.monitoring == 'prometheus':
        collector = PrometheusCollector(8080)
    elif opts.monitoring == 'splunk':
        collector = SplunkCollector()
    else:
        collector = NullCollector()

    # Choose video source
    if opts.infile is None:
        zpc = VideoCapture(stream_address=opts.webcam, out_key=opts.output,
                           metrics_collector=collector, fps=opts.fps, maxlen=opts.maxlen,
                           use_memory=opts.shared)
    else:
        zpc = VideoCapture(stream_address=opts.infile, out_key=opts.output,
                           metrics_collector=collector, fps=opts.fps, maxlen=opts.maxlen,
                           use_memory=opts.shared)
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
