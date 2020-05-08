from pipert.core.routine import Routine, RoutineTypes
from pipert.core import QueueHandler
from queue import Empty, Full
from pipert.utils.visualizer import VideoVisualizer
from detectron2.data import MetadataCatalog
from typing import Optional
from pipert.core.message import Message
import cv2
import time


class VisLogic(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = QueueHandler(in_queue)
        self.out_queue = QueueHandler(out_queue)
        self.vis = VideoVisualizer(MetadataCatalog.get("coco_2017_train"))
        self.latest_pred_msg = None

    def main_logic(self, *args, **kwargs):
        messages = self.in_queue.non_blocking_get()
        if messages:
            frame_msg, pred_msg = messages
            if pred_msg is not None:
                self.latest_pred_msg = pred_msg
            pred_msg = self.latest_pred_msg
            self.draw_preds_on_frame(frame_msg, pred_msg)
            self.pass_frame_to_flask(frame_msg, pred_msg)
            return True
        else:
            return None

    def draw_preds_on_frame(self, frame_msg, pred_msg: Optional[Message]):
        if pred_msg is not None and not pred_msg.is_empty():
            frame = frame_msg.get_payload()
            pred = pred_msg.get_payload()
            image = self.vis.draw_instance_predictions(frame, pred) \
                .get_image()
            frame_msg.update_payload(image)

    def pass_frame_to_flask(self, frame_msg, pred_msg: Optional[Message]):
        image = frame_msg.get_payload()
        _, frame = cv2.imencode('.jpg', image)
        frame = frame.tobytes()
        frame_msg.record_exit(self.component_name, self.logger)
        if pred_msg is not None and not pred_msg.reached_exit:
            pred_msg.record_exit(self.component_name, self.logger)
            latency = pred_msg.get_end_to_end_latency(self.component_name)
            if latency is not None:
                self.metrics_collector.collect_latency(latency, self.component_name)
        success = self.out_queue.deque_non_blocking_put(frame)
        return success

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "in_queue": "Queue",
            "out_queue": "Queue",
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return (self.in_queue == queue) or (self.out_queue == queue)
