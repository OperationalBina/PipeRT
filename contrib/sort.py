from contrib.sort_tracker.sort import Sort
import torch
from detectron2.structures import Instances, Boxes
import numpy as np
from src.base import BaseComponent
from queue import Queue, Empty
import argparse
from urllib.parse import urlparse
import zerorpc
import gevent
import signal
import time
from src.core.routine_engine import RoutineMixin
from src.core.mini_logics import add_logic_to_thread, Metadata2Redis, MetadataFromRedis


class InstancesSort(Sort):

    def __init__(self, max_age: int = 1, min_hits: int = None, window_size: int = None, percent_seen: float = None,
                 verbose: bool = False):
        super().__init__(max_age, min_hits, window_size, percent_seen, verbose)

    def update_instances(self, instances: Instances):
        im_size = instances.image_size
        tracks = None
        if len(instances):
            boxes = instances.get("pred_boxes").tensor.cpu().numpy()
            scores = instances.get("scores").cpu().unsqueeze(1).numpy()
            pred_classes = instances.get("pred_classes").cpu().unsqueeze(1).numpy()
            dets = np.concatenate((boxes, scores, pred_classes), axis=1)
            tracks = self.update(dets)

        ret_tracks = Instances(im_size)
        if tracks is not None:
            tracks = torch.tensor(tracks)
            ret_tracks.set("pred_boxes", Boxes(tracks[:, :4]))
            ret_tracks.set("scores", tracks[:, 4])
            if tracks.shape[0] != 0:
                ret_tracks.set("pred_classes", tracks[:, 5].round().int())
                ret_tracks.set("track_ids", tracks[:, -1].int())

        return ret_tracks


class SORTLogic(RoutineMixin):

    def __init__(self, stop_event, in_queue, out_queue, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.sort = InstancesSort(*args, **kwargs)

    def main_logic(self, *args, **kwargs):
        try:
            instances = self.in_queue.get(block=False)
            new_instances = self.sort.update_instances(instances)
            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            self.out_queue.put(new_instances)
            return True
            # except Full:

                # return False

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass


class SORTComponent(BaseComponent):

    def __init__(self, in_key, out_key, redis_url, maxlen=100, *args, **kwargs):
        super().__init__(out_key, in_key)
        # TODO: should queue maxsize be configurable?
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)
        t_get_meta_class = add_logic_to_thread(MetadataFromRedis)
        t_sort_class = add_logic_to_thread(SORTLogic)
        t_upload_meta_class = add_logic_to_thread(Metadata2Redis)

        t_get_meta = t_get_meta_class(self.stop_event, in_key, redis_url, self.in_queue, "instances")
        t_sort = t_sort_class(self.stop_event, self.in_queue, self.out_queue, *args, **kwargs)
        t_upload_meta = t_upload_meta_class(self.stop_event, out_key, redis_url, self.out_queue, "instances", maxlen,
                                            name="upload_redis")

        self.thread_list = [t_get_meta, t_sort, t_upload_meta]
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
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:2')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:3')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4247')
    parser.add_argument('--field', help='Image field name', type=str, default='instances')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    # max_age: int = 1, min_hits: int = None, window_size: int = None, percent_seen
    parser.add_argument('--max-age', type=int, default=1, help='object confidence threshold')
    parser.add_argument('--min-hits', type=int, help='iou threshold for non-maximum suppression')
    parser.add_argument('--window-size', type=int, default='mp4v', help='output video codec (verify ffmpeg support)')
    parser.add_argument('--percent-seen', type=float, help='output video codec (verify ffmpeg support)')
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = zerorpc.Server(SORTComponent(opt.input, opt.output, url, opt.maxlen, opt.max_age, opt.min_hits,
                                       opt.window_size, opt.percent_seen))
    zpc.bind(f"tcp://0.0.0.0:{opt.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
