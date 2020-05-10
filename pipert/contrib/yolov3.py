import argparse
from queue import Queue
from urllib.parse import urlparse
# from sys import platform
from pipert.contrib.detection_demo.models import *  # set ONNX_EXPORT in models.py
# from detection_demo.utils.datasets import *
from pipert.contrib.detection_demo.utils import *
from pipert.contrib.metrics_collectors.prometheus_collector import PrometheusCollector
from pipert.core.message import PredictionPayload
from pipert.contrib.metrics_collectors.splunk_collector import SplunkCollector
from pipert.core.metrics_collector import NullCollector
from pipert.utils.structures import Instances, Boxes
from pipert.core import Routine, BaseComponent, QueueHandler, RoutineTypes
from pipert.contrib.routines import BatchMessageFromRedis, BatchMessageToRedis, YoloV3Logic, MessageFromRedis, \
    MessageToRedis


class YoloV3(BaseComponent):

    def __init__(self, in_key, out_key, maxlen, metrics_collector, name="YoloV3"):
        super().__init__(name, metrics_collector)
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)
        t_get = MessageFromRedis(in_key, self.in_queue, name="get_frames", component_name=self.name,
                                 metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_get)
        t_det = YoloV3Logic(self.in_queue, self.out_queue, opt.cfg, opt.names, opt.weights, opt.img_size,
                            opt.conf_thres, opt.nms_thres, opt.half, False, name='yolo_logic',
                            component_name=self.name, metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_det)
        t_send = MessageToRedis(out_key, self.out_queue, maxlen, name="upload_redis", component_name=self.name,
                                metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_send)


class YoloV3Batch(BaseComponent):

    def __init__(self, src_dst_keys, maxlen, metrics_collector, name="YoloV3Batch"):
        super().__init__(name, metrics_collector)
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)

        t_get_batch = BatchMessageFromRedis(src_dst_keys, self.in_queue, name="get_frames", component_name=self.name,
                                            metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_get_batch)

        t_det = YoloV3Logic(self.in_queue, self.out_queue, opt.cfg, opt.names, opt.weights, opt.img_size,
                            opt.conf_thres, opt.nms_thres, opt.half, True, name='yolo_logic',
                            component_name=self.name, metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_det)

        t_send_batch = BatchMessageToRedis(src_dst_keys, self.out_queue, maxlen, name="upload_redis",
                                           component_name=self.name,
                                           metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_send_batch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, default='pipert/contrib/YoloResources/yolov3.cfg', help='cfg file path')
    parser.add_argument('--names', type=str, default='pipert/contrib/YoloResources/coco.names',
                        help='coco.names file path')
    parser.add_argument('--weights', type=str, default='pipert/contrib/YoloResources/yolov3.weights',
                        help='path to weights file')
    parser.add_argument('--source', type=str, default='0', help='source')  # input file/folder, 0 for webcam
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:2')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4243')
    parser.add_argument('-b', '--batch', help='batching mechanism', type=bool, default=False)
    parser.add_argument('--monitoring', help='Name of the monitoring service', type=str, default='prometheus')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    parser.add_argument('--img-size', type=int, default=416, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.3, help='object confidence threshold')
    parser.add_argument('--nms-thres', type=float, default=0.5, help='iou threshold for non-maximum suppression')
    parser.add_argument('--fourcc', type=str, default='mp4v', help='output video codec (verify ffmpeg support)')
    parser.add_argument('--half', action='store_true', help='half precision FP16 inference')
    opt = parser.parse_args()

    # url = urlparse(opts.url)
    url = os.environ.get('REDIS_URL')
    url = urlparse(url) if url is not None else urlparse(opt.url)

    if opt.monitoring == 'prometheus':
        collector = PrometheusCollector(8081)
    elif opt.monitoring == 'splunk':
        collector = SplunkCollector()
    else:
        collector = NullCollector()

    if not opt.batch:
        zpc = YoloV3(opt.input, opt.output, opt.maxlen, collector)
    else:
        src_dst_keys = [(opt.input, opt.output)]
        zpc = YoloV3Batch(src_dst_keys, opt.maxlen, collector)
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
