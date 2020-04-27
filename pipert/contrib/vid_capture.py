import cv2
from imutils import resize
from pipert import BaseComponent, Routine
from queue import Queue
import argparse
from urllib.parse import urlparse
import os

from pipert.contrib.metrics_collectors.prometheus_collector import PrometheusCollector
from pipert.core.message import Message
from pipert.core.metrics_collector import NullCollector
from pipert.core.mini_logics import Message2Redis
from pipert.core import QueueHandler
from pipert.contrib.metrics_collectors.splunk_collector import SplunkCollector


class Listen2Stream(Routine):

    def __init__(self, stream_address, queue, fps=30., use_memory=False,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_address = stream_address
        self.is_file = str(stream_address).endswith("mp4")
        self.stream = None
        # self.stream = cv2.VideoCapture(self.stream_address)
        self.q_handler = QueueHandler(queue)
        self.fps = fps
        self.updated_config = {}

    def begin_capture(self):
        self.stream = cv2.VideoCapture(self.stream_address)
        if self.is_file:
            self.fps = self.stream.get(cv2.CAP_PROP_FPS)
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        _, _ = self.grab_frame()
        self.logger.info("Starting video capture on %s", self.stream_address)

    def change_stream(self):
        if self.stream_address == self.updated_config['stream_address']:
            return
        self.stream_address = self.updated_config['stream_address']
        self.fps = self.updated_config['FPS']
        self.is_file = str(self.stream_address).endswith("mp4")
        self.logger.info("Changing source stream address to %s",
                         self.updated_config['stream_address'])
        self.begin_capture()

    def grab_frame(self):
        grabbed, frame = self.stream.read()
        msg = Message(frame, self.stream_address)
        msg.record_entry(self.component_name, self.logger)
        return grabbed, msg

    def main_logic(self, *args, **kwargs):
        if self.updated_config:
            self.change_stream()
            self.updated_config = {}

        grabbed, frame = self.stream.read()
        if grabbed:
            msg = Message(frame, self.stream_address)
            msg.record_entry(self.component_name, self.logger)

            frame = resize(frame, 640, 480)
            # if the stream is from a webcam, flip the frame
            if self.stream_address == 0:
                frame = cv2.flip(frame, 1)
            msg.update_payload(frame)

            success = self.q_handler.deque_non_blocking_put(msg)
            return success

    def setup(self, *args, **kwargs):
        self.begin_capture()

    def cleanup(self, *args, **kwargs):
        self.stream.release()
        del self.stream


class VideoCapture(BaseComponent):

    def __init__(self, endpoint, stream_address, out_key, redis_url, metrics_collector, use_memory=False, fps=30.0,
                 maxlen=10, name="VideoCapture"):
        super().__init__(endpoint, name, metrics_collector, use_memory=use_memory)
        # TODO: should queue maxsize be configurable?
        self.queue = Queue(maxsize=10)

        t_stream = Listen2Stream(stream_address, self.queue, fps, name="capture_frame", component_name=self.name,
                                 metrics_collector=self.metrics_collector) \
            .as_thread()
        t_stream.pace(fps)
        self.register_routine(t_stream)

        t_upload = Message2Redis(out_key, redis_url, self.queue, maxlen, name="upload_redis", component_name=self.name,
                                 metrics_collector=self.metrics_collector) \
            .as_thread()
        self.register_routine(t_upload)

    def change_stream(self, stream_address, fps=30.0):
        self._routines[0].updated_config = {"stream_address": stream_address, "FPS": fps}


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
        zpc = VideoCapture(endpoint="tcp://0.0.0.0:4242", stream_address=opts.webcam, out_key=opts.output,
                           redis_url=url, metrics_collector=collector, fps=opts.fps, maxlen=opts.maxlen,
                           use_memory=opts.shared)
    else:
        zpc = VideoCapture(endpoint="tcp://0.0.0.0:4242", stream_address=opts.infile, out_key=opts.output,
                           redis_url=url, metrics_collector=collector, fps=opts.fps, maxlen=opts.maxlen,
                           use_memory=opts.shared)
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
