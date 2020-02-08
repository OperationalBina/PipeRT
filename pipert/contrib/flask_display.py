import argparse
import redis
from urllib.parse import urlparse
from flask import Flask, Response, request
from pipert.core.component import BaseComponent
from pipert.core.routine import Routine
from queue import Empty, Full
from multiprocessing import Process, Queue
import cv2
from pipert.utils.visualizer import VideoVisualizer
from detectron2.data import MetadataCatalog
from pipert.core.message import message_decode
import time
import requests


def gen(q):
    while True:
        try:
            msg = q.get(block=False)
            image = msg.get_payload()
            ret, frame = cv2.imencode('.jpg', image)
            frame = frame.tobytes()
            yield (b'--frame\r\n'
                   b'Pragma-directive: no-cache\r\n'
                   b'Cache-directive: no-cache\r\n'
                   b'Cache-control: no-cache\r\n'
                   b'Pragma: no-cache\r\n'
                   b'Expires: 0\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        except Empty:
            time.sleep(0)


class MetaAndFrameFromRedis(Routine):

    def __init__(self, in_key_meta, in_key_im, url, queue, field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key_meta = in_key_meta
        self.in_key_im = in_key_im
        self.url = url
        self.queue = queue
        self.field = field.encode('utf-8')
        self.conn = None
        self.flip = False
        self.negative = False

    def receive_msg(self, in_key, msg_key):
        # TODO - refactor to use xread instead of xrevrange
        encoded_msg = self.conn.xrevrange(in_key, count=1)
        if not encoded_msg:
            return None
        msg = message_decode(encoded_msg[0][1][msg_key.encode("utf-8")])
        msg.record_entry(self.component_name)
        self.logger.info("Received the following message: %s", str(msg))
        return msg

    def main_logic(self, *args, **kwargs):
        pred_msg = self.receive_msg(self.in_key_meta, "pred_msg")
        frame_msg = self.receive_msg(self.in_key_im, "frame_msg")
        if frame_msg:
            arr = frame_msg.get_payload()
            if len(arr.shape) == 3:
                arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)

            if self.flip:
                arr = cv2.flip(arr, 1)

            if self.negative:
                arr = 255 - arr

            try:
                self.queue.get(block=False)
            except Empty:
                pass
            frame_msg.update_payload(arr)
            self.queue.put((frame_msg, pred_msg))
            return True

        else:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.conn = redis.Redis(host=self.url.hostname, port=self.url.port)
        if not self.conn.ping():
            raise Exception('Redis unavailable')

    def cleanup(self, *args, **kwargs):
        self.conn.close()


class VisLogic(Routine):
    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.vis = VideoVisualizer(MetadataCatalog.get("coco_2017_train"))

    def main_logic(self, *args, **kwargs):
        # TODO implement input that takes both frame and metadata
        try:
            frame_msg, pred_msg = self.in_queue.get(block=False)
            if pred_msg is not None:
                frame = frame_msg.get_payload()
                pred = pred_msg.get_payload()
                image = self.vis.draw_instance_predictions(frame, pred)\
                    .get_image()
                frame_msg.update_payload(image)
                frame_msg.history = pred_msg.history
                frame_msg.record_exit(self.component_name)
            try:
                self.out_queue.put(frame_msg, block=False)
                return True
            except Full:
                try:
                    self.out_queue.get(block=False)
                    self.state.dropped += 1
                except Empty:
                    pass
                finally:
                    try:
                        self.out_queue.put(frame_msg, block=False)
                    except Full:
                        pass
                    return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass


class FlaskVideoDisplay(BaseComponent):

    def __init__(self, in_key_meta, in_key_im, redis_url, field, endpoint,
                 name="FlaskVideoDisplay"):
        super().__init__(endpoint, name)
        self.field = field  # .encode('utf-8')
        self.queue = Queue(maxsize=1)
        self.t_get = MetaAndFrameFromRedis(in_key_meta, in_key_im, redis_url,
                                           self.queue, self.field,
                                           name="get_frames",
                                           component_name=self.name)
        self.t_get.as_thread()
        self.register_routine(self.t_get)

        self.queue2 = Queue(maxsize=1)
        self.t_vis = VisLogic(self.queue, self.queue2,
                              component_name=self.name).as_thread()
        self.register_routine(self.t_vis)

        app = Flask(__name__)

        @app.route('/video')
        def video_feed():
            return Response(gen(self.queue2),
                            mimetype='multipart/x-mixed-replace; '
                                     'boundary=frame')

        def shutdown_server():
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()

        @app.route('/shutdown')
        def shutdown():
            # app.do_teardown_appcontext()
            shutdown_server()
            return 'Server shutting down...'

        self.server = Process(target=app.run, kwargs={"host": '0.0.0.0'})
        self.register_routine(self.server)

    def _teardown_callback(self, *args, **kwargs):
        # self.server.terminate()
        _ = requests.get("http://127.0.0.1:5000/shutdown")
        self.server.terminate()
        # print("kill!!!")
        # self.server.kill()

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
    parser.add_argument('--field', help='Image field name', type=str, default='image')
    args = parser.parse_args()

    # Set up Redis connection
    url = urlparse(args.url)
    conn = redis.Redis(host=url.hostname, port=url.port)
    if not conn.ping():
        raise Exception('Redis unavailable')
    zpc = FlaskVideoDisplay(args.input_meta, args.input_im, url, args.field, endpoint=f"tcp://0.0.0.0:{args.zpc}")
    print("run flask")
    zpc.run()
    print("Killed")
