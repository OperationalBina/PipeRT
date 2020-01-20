from pipert import BaseComponent
from queue import Queue
# from torch.multiprocessing import Queue
import argparse
from urllib.parse import urlparse
from pipert.core.mini_logics import Frames2Redis, Listen2Stream


class VideoCapture(BaseComponent):

    def __init__(self, endpoint, stream_address, out_key, redis_url, fps=30.0, maxlen=10):
        super().__init__(endpoint)
        # TODO: should queue maxsize be configurable?
        # self.queue = Queue(maxsize=1)
        self.queue = Queue(maxsize=1)

        t_stream = Listen2Stream(stream_address, self.queue, fps, name="capture_frame").as_thread()
        self.register_routine(t_stream)
        t_upload = Frames2Redis(out_key, redis_url, self.queue, maxlen, name="upload_redis").as_thread()
        self.register_routine(t_upload)

    def changeStream(self, stream_address, fps=30.0):
        self._routines[0].updatedConfig = {"stream_address": stream_address, "FPS": fps}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', help='Input file (leave empty to use webcam)', nargs='?', type=str,
                        default=None)
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
        zpc = VideoCapture(endpoint="tcp://0.0.0.0:4242", stream_address=args.webcam, out_key=args.output,
                           redis_url=url, fps=args.fps, maxlen=args.maxlen)
    else:
        zpc = VideoCapture(endpoint="tcp://0.0.0.0:4242", stream_address=args.infile, out_key=args.output,
                           redis_url=url, fps=args.fps, maxlen=args.maxlen)
    print("run")
    zpc.run()
    print("Killed")
