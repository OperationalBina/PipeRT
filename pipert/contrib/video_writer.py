import cv2
from pipert import BaseComponent, Routine
from queue import Queue
import argparse
from urllib.parse import urlparse
from imutils import resize
from pipert.core.mini_logics import MessageFromRedis
from pipert.core import QueueHandler, Message


class VideoWriterLogic(Routine):

    def __init__(self, output_file, in_queue, fps=30, im_size=(640, 480), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.writer = None
        self.output_file = output_file
        self.q_handler = QueueHandler(in_queue)
        self.w, self.h = im_size
        self.fps = fps

    def main_logic(self, *args, **kwargs):
        msg: Message = self.q_handler.non_blocking_get()
        if msg:
            frame = msg.get_payload()
            if frame.shape[0] != self.h or frame.shape[1] != self.w:
                self.writer.release()
                self.writer = cv2.VideoWriter(self.output_file, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), self.fps,
                                              (frame.shape[1], frame.shape[0]))
                self.h, self.w = frame.shape[0], frame.shape[1]

            frame = cv2.putText(frame, f"{msg.id.split('_')[-1]}", (0, self.h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                1, (0, 0, 255), 2, cv2.LINE_AA)
            self.writer.write(frame)

    def setup(self, *args, **kwargs):
        self.writer = cv2.VideoWriter(self.output_file, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), self.fps,
                                      (self.w, self.h))

    def cleanup(self, *args, **kwargs):
        self.writer.release()


class VideoWriter(BaseComponent):

    def __init__(self, endpoint, in_key, redis_url, output_file, fps=30, im_size=(640, 480), name="VideoWriter"):
        super().__init__(endpoint, name)
        self.queue = Queue(maxsize=10)
        t_stream = VideoWriterLogic(output_file, self.queue, fps, im_size, name="capture_frame",
                                    component_name=self.name).as_thread()
        t_stream.pace(30)
        self.register_routine(t_stream)
        t_upload = MessageFromRedis(in_key, redis_url, self.queue, most_recent=False, name="upload_redis",
                                    component_name=self.name).as_thread()
        self.register_routine(t_upload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--in-key', help='Input key', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output file name', type=str, default='output.avi')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('--fps', help='Frames per second', type=int, default=30)
    parser.add_argument('--width', help='frame width', type=int, default=640)
    parser.add_argument('--height', help='frame height', type=int, default=480)
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4248')
    opts = parser.parse_args()

    # Set up Redis connection
    url = urlparse(opts.url)

    # Choose video source
    zpc = VideoWriter(endpoint=f"tcp://0.0.0.0:{opts.zpc}",  in_key=opts.in_key, redis_url=url, output_file=opts.output,
                      fps=opts.fps, im_size=(opts.width, opts.height))
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
