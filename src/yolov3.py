import argparse
# from sys import platform
from detection_demo.models import *  # set ONNX_EXPORT in models.py
# from detection_demo.utils.datasets import *
from detection_demo.parse_config import parse_data_cfg
from detection_demo.utils import *
from detection_demo import torch_utils
from core.routine_engine import RoutineMixin
from core.mini_logics import FramesFromRedis, Frames2Redis, add_logic_to_thread
from base import BaseComponent
import time
from queue import Empty, Queue, Full
from urllib.parse import urlparse
import zerorpc
import gevent
import signal


def letterbox(img, new_shape=416, color=(128, 128, 128), mode='auto'):
    # Resize a rectangular image to a 32 pixel multiple rectangle
    # https://github.com/ultralytics/yolov3/issues/232
    shape = img.shape[:2]  # current shape [height, width]

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

    if shape[::-1] != new_unpad:  # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_AREA)  # INTER_AREA is better, INTER_LINEAR is faster
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return img, ratiow, ratioh, dw, dh


class YoloV3Logic(RoutineMixin):

    def __init__(self, stop_event, in_queue, out_queue, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
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
        self.classes = load_classes(parse_data_cfg(opt.data)['names'])
        self.colors = [[random.randint(0, 255) for _ in range(3)] for _ in range(len(self.classes))]
        self.device = device

    def main_logic(self, *args, **kwargs):
        try:
            im0 = self.in_queue.get(block=False)
            img, *_ = letterbox(im0, new_shape=self.img_size)

            # Normalize RGB
            img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB
            img = np.ascontiguousarray(img, dtype=np.float16 if self.half else np.float32)  # uint8 to fp16/fp32
            img /= 255.0
            img = torch.from_numpy(img).to(self.device)
            # print(f"yolo {self.device}")
            if img.ndimension() == 3:
                img = img.unsqueeze(0)
            with torch.no_grad():
                pred, _ = self.model(img)
            for i, det in enumerate(non_max_suppression(pred, opt.conf_thres, opt.nms_thres)):
                if det is not None and len(det):
                    # Rescale boxes from img_size to im0 size
                    det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                    for *xyxy, conf, _, cls in det:
                        label = '%s %.2f' % (self.classes[int(cls)], conf)
                        plot_one_box(xyxy, im0, label=label, color=self.colors[int(cls)])
            while True:
                try:
                    self.out_queue.put(im0)
                    break
                except Full:
                    time.sleep(0)
        except Empty:
            time.sleep(0)

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass


class YoloV3(BaseComponent):

    def __init__(self, out_key, in_key, redis_url, field, maxlen):
        #TODO - is field really needed? needs testing
        super().__init__(out_key, in_key)
        self.field = field
        self.in_queue = Queue(maxsize=10)
        self.out_queue = Queue(maxsize=10)
        t_get_class = add_logic_to_thread(FramesFromRedis)
        t_det_class = add_logic_to_thread(YoloV3Logic)
        t_send_class = add_logic_to_thread(Frames2Redis)

        t_get = t_get_class(self.stop_event, in_key, redis_url, self.in_queue, self.field)
        t_det = t_det_class(self.stop_event, self.in_queue, self.out_queue)
        t_send = t_send_class(self.stop_event, out_key, redis_url, self.out_queue, maxlen)

        self.thread_list = [t_get, t_det, t_send]
        self._start()

    def _start(self):
        for t in self.thread_list:
            t.daemon = True
            t.start()
        return self

    def _inner_stop(self):
        for t in self.thread_list:
            t.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg', type=str, default='/home/itamar/PycharmProjects/Inference/src/yolov3_demo/yolov3.cfg', help='cfg file path')
    parser.add_argument('--data', type=str, default='/home/itamar/PycharmProjects/Inference/src/yolov3_demo/coco.data', help='coco.data file path')
    parser.add_argument('--weights', type=str, default='/home/itamar/PycharmProjects/Inference/src/yolov3_demo/yolov3.weights', help='path to weights file')
    parser.add_argument('--source', type=str, default='0', help='source')  # input file/folder, 0 for webcam
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:1')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4245')
    parser.add_argument('--field', help='Image field name', type=str, default='image')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    parser.add_argument('--img-size', type=int, default=416, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.3, help='object confidence threshold')
    parser.add_argument('--nms-thres', type=float, default=0.5, help='iou threshold for non-maximum suppression')
    parser.add_argument('--fourcc', type=str, default='mp4v', help='output video codec (verify ffmpeg support)')
    parser.add_argument('--half', action='store_true', help='half precision FP16 inference')
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = zerorpc.Server(YoloV3(opt.output, opt.input, url, opt.field, opt.maxlen))
    zpc.bind(f"tcp://0.0.0.0:{opt.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")
