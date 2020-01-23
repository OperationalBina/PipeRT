from pipert.contrib.sort_tracker.sort import Sort
import torch
from pipert.utils.structures import Instances, Boxes
import numpy as np
from pipert.core.component import BaseComponent
from queue import Queue, Empty
import argparse
from urllib.parse import urlparse
import time
from pipert.core.routine import Routine
from pipert.core.mini_logics import Metadata2Redis, MetadataFromRedis


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


class SORTLogic(Routine):

    def __init__(self, in_queue, out_queue, component_name, *args, **kwargs):
        super().__init__(component_name=component_name)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.sort = InstancesSort(*args, **kwargs)

    def main_logic(self, *args, **kwargs):
        try:
            pred_msg = self.in_queue.get(block=False)
            instances = pred_msg.payload.data
            new_instances = self.sort.update_instances(instances)
            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            pred_msg.update_payload(new_instances)
            self.out_queue.put(pred_msg)
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

    def __init__(self, endpoint, in_key, out_key, redis_url, maxlen=100, name="SORTComponent", *args, **kwargs):
        super().__init__(endpoint, name)
        # TODO: should queue maxsize be configurable?
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)

        t_get_meta = MetadataFromRedis(in_key, redis_url, self.in_queue, "instances", component_name=self.name).as_thread()
        self.register_routine(t_get_meta)
        t_sort = SORTLogic(self.in_queue, self.out_queue, component_name=self.name, *args, **kwargs).as_thread()
        self.register_routine(t_sort)
        t_upload_meta = Metadata2Redis(out_key, redis_url, self.out_queue, "instances", maxlen,
                                       name="upload_redis").as_thread()
        self.register_routine(t_upload_meta)


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
    parser.add_argument('--window-size', type=int, default='1', help='output video codec (verify ffmpeg support)')
    parser.add_argument('--percent-seen', type=float, help='output video codec (verify ffmpeg support)')
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = SORTComponent(f"tcp://0.0.0.0:{opt.zpc}", opt.input, opt.output, url, opt.maxlen, opt.max_age, opt.min_hits,
                        opt.window_size, opt.percent_seen)
    print("run")
    zpc.run()
    print("Killed")
