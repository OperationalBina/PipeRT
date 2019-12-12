import torch
import torch.nn as nn
import numpy as np
from queue import Empty, Queue
import time
from scipy.signal.windows import gaussian
from base import BaseComponent
from core.routine_engine import RoutineMixin, Events
from core.handlers import tick, tock
from core.mini_logics import add_logic_to_thread, FramesFromRedis, Frames2Redis
import zerorpc
import argparse
from urllib.parse import urlparse
import gevent
import signal
import logging


class Net(nn.Module):
    def __init__(self, threshold=10.0, use_cuda=False):
        super(Net, self).__init__()

        self.threshold = threshold
        self.use_cuda = use_cuda

        filter_size = 5
        generated_filters = gaussian(filter_size, std=1.0).reshape([1, filter_size])

        self.gaussian_filter_horizontal = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=(1, filter_size),
                                                    padding=(0, filter_size // 2))
        self.gaussian_filter_horizontal.weight.data.copy_(torch.from_numpy(generated_filters))
        self.gaussian_filter_horizontal.bias.data.copy_(torch.from_numpy(np.array([0.0])))
        self.gaussian_filter_vertical = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=(filter_size, 1),
                                                  padding=(filter_size // 2, 0))
        self.gaussian_filter_vertical.weight.data.copy_(torch.from_numpy(generated_filters.T))
        self.gaussian_filter_vertical.bias.data.copy_(torch.from_numpy(np.array([0.0])))

        sobel_filter = np.array([[1, 0, -1],
                                 [2, 0, -2],
                                 [1, 0, -1]])

        self.sobel_filter_horizontal = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=sobel_filter.shape,
                                                 padding=sobel_filter.shape[0] // 2)
        self.sobel_filter_horizontal.weight.data.copy_(torch.from_numpy(sobel_filter))
        self.sobel_filter_horizontal.bias.data.copy_(torch.from_numpy(np.array([0.0])))
        self.sobel_filter_vertical = nn.Conv2d(in_channels=1, out_channels=1, kernel_size=sobel_filter.shape,
                                               padding=sobel_filter.shape[0] // 2)
        self.sobel_filter_vertical.weight.data.copy_(torch.from_numpy(sobel_filter.T))
        self.sobel_filter_vertical.bias.data.copy_(torch.from_numpy(np.array([0.0])))

        # filters were flipped manually
        filter_0 = np.array([[0, 0, 0],
                             [0, 1, -1],
                             [0, 0, 0]])

        filter_45 = np.array([[0, 0, 0],
                              [0, 1, 0],
                              [0, 0, -1]])

        filter_90 = np.array([[0, 0, 0],
                              [0, 1, 0],
                              [0, -1, 0]])

        filter_135 = np.array([[0, 0, 0],
                               [0, 1, 0],
                               [-1, 0, 0]])

        filter_180 = np.array([[0, 0, 0],
                               [-1, 1, 0],
                               [0, 0, 0]])

        filter_225 = np.array([[-1, 0, 0],
                               [0, 1, 0],
                               [0, 0, 0]])

        filter_270 = np.array([[0, -1, 0],
                               [0, 1, 0],
                               [0, 0, 0]])

        filter_315 = np.array([[0, 0, -1],
                               [0, 1, 0],
                               [0, 0, 0]])

        all_filters = np.stack(
            [filter_0, filter_45, filter_90, filter_135, filter_180, filter_225, filter_270, filter_315])

        self.directional_filter = nn.Conv2d(in_channels=1, out_channels=8, kernel_size=filter_0.shape,
                                            padding=filter_0.shape[-1] // 2)
        self.directional_filter.weight.data.copy_(torch.from_numpy(all_filters[:, None, ...]))
        self.directional_filter.bias.data.copy_(torch.from_numpy(np.zeros(shape=(all_filters.shape[0],))))

    def forward(self, img):
        img_r = img[:, 0:1]
        img_g = img[:, 1:2]
        img_b = img[:, 2:3]

        blur_horizontal = self.gaussian_filter_horizontal(img_r)
        blurred_img_r = self.gaussian_filter_vertical(blur_horizontal)
        blur_horizontal = self.gaussian_filter_horizontal(img_g)
        blurred_img_g = self.gaussian_filter_vertical(blur_horizontal)
        blur_horizontal = self.gaussian_filter_horizontal(img_b)
        blurred_img_b = self.gaussian_filter_vertical(blur_horizontal)

        blurred_img = torch.stack([blurred_img_r, blurred_img_g, blurred_img_b], dim=1)
        blurred_img = torch.stack([torch.squeeze(blurred_img)])

        grad_x_r = self.sobel_filter_horizontal(blurred_img_r)
        grad_y_r = self.sobel_filter_vertical(blurred_img_r)
        grad_x_g = self.sobel_filter_horizontal(blurred_img_g)
        grad_y_g = self.sobel_filter_vertical(blurred_img_g)
        grad_x_b = self.sobel_filter_horizontal(blurred_img_b)
        grad_y_b = self.sobel_filter_vertical(blurred_img_b)

        # COMPUTE THICK EDGES

        grad_mag = torch.sqrt(grad_x_r ** 2 + grad_y_r ** 2)
        grad_mag += torch.sqrt(grad_x_g ** 2 + grad_y_g ** 2)
        grad_mag += torch.sqrt(grad_x_b ** 2 + grad_y_b ** 2)
        grad_orientation = (
                    torch.atan2(grad_y_r + grad_y_g + grad_y_b, grad_x_r + grad_x_g + grad_x_b) * (180.0 / 3.14159))
        grad_orientation += 180.0
        grad_orientation = torch.round(grad_orientation / 45.0) * 45.0

        # THIN EDGES (NON-MAX SUPPRESSION)

        all_filtered = self.directional_filter(grad_mag)

        inidices_positive = (grad_orientation / 45) % 8
        inidices_negative = ((grad_orientation / 45) + 4) % 8

        height = inidices_positive.size()[2]
        width = inidices_positive.size()[3]
        pixel_count = height * width
        pixel_range = torch.arange(0, pixel_count).float().view(1, -1)
        # pixel_range = torch.FloatTensor([range(pixel_count)])
        if self.use_cuda:
            pixel_range = pixel_range.cuda()
            # pixel_range = torch.cuda.FloatTensor([range(pixel_count)])

        indices = (inidices_positive.view(-1).data * pixel_count + pixel_range).squeeze()
        channel_select_filtered_positive = all_filtered.view(-1)[indices.long()].view(1, height, width)

        indices = (inidices_negative.view(-1).data * pixel_count + pixel_range).squeeze()
        channel_select_filtered_negative = all_filtered.view(-1)[indices.long()].view(1, height, width)

        channel_select_filtered = torch.stack([channel_select_filtered_positive, channel_select_filtered_negative])

        is_max = channel_select_filtered.min(dim=0)[0] > 0.0
        is_max = torch.unsqueeze(is_max, dim=0)

        thin_edges = grad_mag.clone()
        thin_edges[is_max == 0] = 0.0

        # THRESHOLD

        thresholded = thin_edges.clone()
        thresholded[thin_edges < self.threshold] = 0.0
        thresholded[thin_edges >= self.threshold] = 255

        early_threshold = grad_mag.clone()
        early_threshold[grad_mag < self.threshold] = 0.0

        # return blurred_img, grad_mag, grad_orientation, thin_edges, thresholded, early_threshold
        return thresholded


class CannyLogic(RoutineMixin):

    def __init__(self, stop_event, in_queue, out_queue, use_cuda, *args, **kwargs):
        super().__init__(stop_event, *args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.use_cuda = use_cuda
        self.model = Net(5., use_cuda=self.use_cuda)
        if self.use_cuda:
            self.model.cuda()
        print(self.use_cuda)

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.in_queue.get(block=False)
            frame = torch.from_numpy(frame.transpose((2, 0, 1))) / 255.
            if self.use_cuda:
                frame = frame.cuda()
                # print("canny cuda")
            outputs = self.model(frame.unsqueeze(0))
            outputs = outputs.squeeze(0).data.cpu().numpy()
            # while True:
            # try:
            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            self.out_queue.put(outputs[0])
            return True
            # except Full:

                # return False

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.model.eval()
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass


class Canny(BaseComponent):

    def __init__(self, out_key, in_key, redis_url, field, maxlen):
        # TODO - is field really needed? needs testing
        super().__init__(out_key, in_key)
        self.field = field
        self.in_queue = Queue(maxsize=10)
        self.out_queue = Queue(maxsize=10)
        t_get_class = add_logic_to_thread(FramesFromRedis)
        t_det_class = add_logic_to_thread(CannyLogic)
        t_send_class = add_logic_to_thread(Frames2Redis)

        t_get = t_get_class(self.stop_event, in_key, redis_url, self.in_queue, self.field, name="get_frames")
        t_det = t_det_class(self.stop_event, self.in_queue, self.out_queue, True, name="canny")
        t_send = t_send_class(self.stop_event, out_key, redis_url, self.out_queue, maxlen, name="send_frames")

        self.thread_list = [t_get, t_det, t_send]
        for t in self.thread_list:
            t.add_event_handler(Events.BEFORE_LOGIC, tick)
            t.add_event_handler(Events.AFTER_LOGIC, tock)

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
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:1')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4245')
    parser.add_argument('--field', help='Image field name', type=str, default='image')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    args = parser.parse_args()

    # Set up Redis connection
    url = urlparse(args.url)

    zpc = zerorpc.Server(Canny(args.output, args.input, url, args.field, args.maxlen))
    zpc.bind(f"tcp://0.0.0.0:{args.zpc}")
    print("run")
    gevent.signal(signal.SIGTERM, zpc.stop)
    zpc.run()
    print("Killed")