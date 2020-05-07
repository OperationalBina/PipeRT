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
from pipert.core.mini_logics import MessageFromRedis, Message2Redis
from pipert.utils.structures import Instances, Boxes
from pipert.core import Routine, BaseComponent, QueueHandler, RoutineTypes
from pipert.contrib.routines import BatchMsgFromRedis, BatchMsgToRedis


def letterbox(imgs, new_shape=416, color=(128, 128, 128), mode='auto'):
    # imgs.shape = (NxWxHxC)
    # Resize a rectangular images to a 32 pixel multiple rectangles
    # https://github.com/ultralytics/yolov3/issues/232
    shape = imgs.shape[1:3]  # current shape [height, width]

    if isinstance(new_shape, int):
        ratio = float(new_shape) / max(shape)
    else:
        ratio = max(new_shape) / max(shape)  # ratio  = new / old
    ratiow, ratioh = ratio, ratio
    new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))

    # Compute padding https://github.com/ultralytics/yolov3/issues/232
    if mode is 'auto':  # minimum rectangle
        dw = np.mod(new_shape - new_unpad[0], 32) / 2  # width padding
        dh = np.mod(new_shape - new_unpad[1], 32) / 2  # height padding
    elif mode is 'square':  # square
        dw = (new_shape - new_unpad[0]) / 2  # width padding
        dh = (new_shape - new_unpad[1]) / 2  # height padding
    elif mode is 'rect':  # square
        dw = (new_shape[1] - new_unpad[0]) / 2  # width padding
        dh = (new_shape[0] - new_unpad[1]) / 2  # height padding
    elif mode is 'scaleFill':
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape, new_shape)
        ratiow, ratioh = new_shape / shape[1], new_shape / shape[0]
    else:
        raise ValueError(f"Unrecognized padding mode {mode}")

    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))

    reshaped = []
    for img in imgs:
        if shape[::-1] != new_unpad:  # resize
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_AREA)  # INTER_AREA is better, INTER_LINEAR is faster
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
        reshaped.append(img)

    return np.array(reshaped), ratiow, ratioh, dw, dh


class YoloV3Logic(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = QueueHandler(in_queue)
        self.out_queue = QueueHandler(out_queue)
        self.img_size = (320, 192) if ONNX_EXPORT else opt.img_size  # (320, 192) or (416, 256) or (608, 352)
        out, source, weights, half = opt.output, opt.source, opt.weights, opt.half
        device = torch_utils.select_device(force_cpu=ONNX_EXPORT)
        self.model = Darknet(opt.cfg, self.img_size)
        if weights.endswith('.pt'):  # pytorch format
            self.model.load_state_dict(torch.load(weights, map_location=device)['model'])
        else:  # darknet format
            _ = load_darknet_weights(self.model, weights)
        self.model.fuse()
        self.model.to(device).eval()
        # Half precision
        self.half = half and device.type != 'cpu'  # half precision only supported on CUDA
        if half:
            self.model.half()
        self.classes = load_classes(opt.names)
        self.colors = [[random.randint(0, 255) for _ in range(3)] for _ in range(len(self.classes))]
        self.device = device

    def main_logic(self, *args, **kwargs):

        batch = self.in_queue.non_blocking_get()
        if batch:
            out_keys = []
            images = []
            for msg in batch:
                out_keys.append(msg.out_key)
                images.append(msg.get_payload())

            im0shape = images[0].shape
            images, *_ = letterbox(np.array(images), new_shape=self.img_size)

            # Normalize RGB
            images = images[:, :, :, ::-1].transpose(0, 3, 1, 2)  # BGR to RGB and switch to NxCxWxH
            images = np.ascontiguousarray(images, dtype=np.float16 if self.half else np.float32)  # uint8 to fp16/fp32
            images /= 255.0
            images = torch.from_numpy(images).to(self.device)

            with torch.no_grad():
                preds, _ = self.model(images)

            dets = non_max_suppression(preds,  opt.conf_thres, opt.nms_thres)

            results = []
            for det in dets:
                if det is not None and len(det):
                    # Rescale boxes from img_size to im0 size
                    det[:, :4] = scale_coords(im0shape[2:], det[:, :4], im0shape).round()
                    # print(det.shape)
                    # print(det)
                    # for *xyxy, conf, _, cls in det:
                    #     label = '%s %.2f' % (self.classes[int(cls)], conf)
                    #     plot_one_box(xyxy, im0, label=label, color=self.colors[int(cls)])
                    res = Instances(im0shape)
                    res.set("pred_boxes", Boxes(det[:, :4]))
                    res.set("scores", det[:, 4])
                    res.set("class_scores", det[:, 5:-1].unsqueeze(1))
                    res.set("pred_classes", det[:, -1].round().int())
                else:
                    res = Instances(im0shape)
                    res.set("pred_boxes", [])
                results.append(res)

            if len(batch) != len(results):
                self.logger.debug(f"Detections missing!! Got a batch of size {len(batch)} "
                                  f"but only have {len(results)} results!")

            snd_batch = {}
            for msg, res in zip(batch, results):
                msg.payload = PredictionPayload(res.to("cpu"))
                snd_batch[msg.out_key] = msg

            success = self.out_queue.deque_non_blocking_put(snd_batch)
            return success

        else:
            return None

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        del self.model, self.device, self.classes, self.colors


class YoloV3(BaseComponent):

    def __init__(self, endpoint, src_dst_keys, maxlen, metrics_collector, name="YoloV3"):
        super().__init__(endpoint, name, metrics_collector)
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)

        t_get_batch = BatchMsgFromRedis(src_dst_keys, self.in_queue, name="get_frames", component_name=self.name,
                                        metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_get_batch)

        t_det = YoloV3Logic(self.in_queue, self.out_queue, name='yolo_logic', component_name=self.name,
                            metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_det)

        t_send_batch = BatchMsgToRedis(src_dst_keys, self.out_queue, maxlen, name="upload_redis", component_name=self.name,
                               metrics_collector=self.metrics_collector).as_thread()
        self.register_routine(t_send_batch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, default='pipert/contrib/YoloResources/yolov3.cfg', help='cfg file path')
    parser.add_argument('--names', type=str, default='pipert/contrib/YoloResources/coco.names', help='coco.names file path')
    parser.add_argument('--weights', type=str, default='pipert/contrib/YoloResources/yolov3.weights', help='path to weights file')
    parser.add_argument('--source', type=str, default='0', help='source')  # input file/folder, 0 for webcam
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:2')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4243')
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

    src_dst_keys =

    zpc = YoloV3(f"tcp://0.0.0.0:{opt.zpc}", src_dst_keys, opt.maxlen, collector)
    print(f"run {zpc.name}")
    zpc.run()
    print(f"Killed {zpc.name}")
