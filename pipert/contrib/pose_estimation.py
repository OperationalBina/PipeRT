import torch
from pipert.core.component import BaseComponent
from queue import Queue, Empty
import argparse
from urllib.parse import urlparse

import time
from pipert.core.routine import Routine
from pipert.core.mini_logics import Message2Redis, MessageFromRedis

# import some common libraries
from detectron2.config import get_cfg
from detectron2.modeling import build_model
import detectron2.data.transforms as T
from detectron2.checkpoint import DetectionCheckpointer
from detectron2.data import MetadataCatalog


class DefaultPredictor:
    """
    Create a simple end-to-end predictor with the given config.
    The predictor takes an BGR image, resizes it to the specified resolution,
    runs the model and produces a dict of predictions.

    Attributes:
        metadata (Metadata): the metadata of the underlying dataset, obtained from
            cfg.DATASETS.TEST.
    """

    def __init__(self, cfg):
        self.cfg = cfg.clone()  # cfg can be modified by model
        self.model = build_model(self.cfg)
        self.model.eval()
        self.metadata = MetadataCatalog.get(cfg.DATASETS.TEST[0])

        checkpointer = DetectionCheckpointer(self.model)
        checkpointer.load(cfg.MODEL.WEIGHTS)

#         self.transform_gen = T.ResizeShortestEdge(
#             [cfg.INPUT.MIN_SIZE_TEST, cfg.INPUT.MIN_SIZE_TEST], cfg.INPUT.MAX_SIZE_TEST
#         )

        self.input_format = cfg.INPUT.FORMAT
        assert self.input_format in ["RGB", "BGR"], self.input_format

    @torch.no_grad()
    def __call__(self, original_image):
        """
        Args:
            original_image (np.ndarray): an image of shape (H, W, C) (in BGR order).

        Returns:
            predictions (dict): the output of the model
        """
        # Apply pre-processing to image.
        if self.input_format == "RGB":
            # whether the model expects BGR inputs or RGB
            original_image = original_image[:, :, ::-1]
        height, width = original_image.shape[:2]
#         image = self.transform_gen.get_transform(original_image).apply_image(original_image)
        image = torch.as_tensor(original_image.astype("float32").transpose(2, 0, 1))

        inputs = {"image": image, "height": height, "width": width}
        predictions = self.model([inputs])[0]
        return predictions


class PoseEstLogic(Routine):

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.cfg = None
        self.predictor = None

    def main_logic(self, *args, **kwargs):
        try:
            frame = self.in_queue.get(block=False)
            outputs = self.predictor(frame)["instances"].to("cpu")

            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            self.out_queue.put(outputs)
            return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.cfg = get_cfg()
        self.cfg.merge_from_file("/home/itamar/PycharmProjects/detectron2_repo/configs/COCO-Keypoints/keypoint_rcnn_R_50_FPN_3x.yaml")
        self.cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7  # set threshold for this model
        self.cfg.MODEL.RPN.PRE_NMS_TOPK_TEST = 100
        self.cfg.MODEL.RPN.Post_NMS_TOPK_TEST = 10
        self.cfg.MODEL.WEIGHTS = "detectron2://COCO-Keypoints/keypoint_rcnn_R_50_FPN_3x/137849621/model_final_a6e10b.pkl"
        self.predictor = DefaultPredictor(self.cfg)

    def cleanup(self, *args, **kwargs):
        pass


class PoseEstComponent(BaseComponent):

    def __init__(self, in_key, out_key, redis_url, maxlen=100, endpoint=""):
        super().__init__(endpoint)
        # TODO: should queue maxsize be configurable?
        self.in_queue = Queue(maxsize=1)
        self.out_queue = Queue(maxsize=1)

        t_get = MessageFromRedis(in_key, redis_url, self.in_queue).as_thread()
        self.register_routine(t_get)
        t_pose = PoseEstLogic(self.in_queue, self.out_queue).as_thread()
        self.register_routine(t_pose)
        t_upload_meta = Message2Redis(out_key, redis_url, self.out_queue, maxlen, name="upload_redis")\
            .as_thread()
        self.register_routine(t_upload_meta)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input stream key name', type=str, default='camera:0')
    parser.add_argument('-o', '--output', help='Output stream key name', type=str, default='camera:3')
    parser.add_argument('-u', '--url', help='Redis URL', type=str, default='redis://127.0.0.1:6379')
    parser.add_argument('-z', '--zpc', help='zpc port', type=str, default='4249')
    parser.add_argument('--maxlen', help='Maximum length of output stream', type=int, default=100)
    # max_age: int = 1, min_hits: int = None, window_size: int = None, percent_seen
    opt = parser.parse_args()

    url = urlparse(opt.url)

    zpc = PoseEstComponent(opt.input, opt.output, url, opt.maxlen, endpoint=f"tcp://0.0.0.0:{opt.zpc}")
    print("run")
    zpc.run()
    print("Killed")
