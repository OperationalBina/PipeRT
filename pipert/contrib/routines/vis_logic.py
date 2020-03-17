from pipert.core.routine import Routine, RoutineTypes
from queue import Empty, Full
from pipert.utils.visualizer import VideoVisualizer
from detectron2.data import MetadataCatalog
import time


class VisLogic(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.vis = VideoVisualizer(MetadataCatalog.get("coco_2017_train"))

    def main_logic(self, *args, **kwargs):
        # TODO implement input that takes both frame and metadata
        try:
            frame_msg, pred_msg = self.in_queue.get(block=False)
            # print("frame", frame_msg)
            # print("pred", pred_msg)
            if pred_msg is not None and not pred_msg.is_empty():
                frame = frame_msg.get_payload()
                pred = pred_msg.get_payload()
                image = self.vis.draw_instance_predictions(frame, pred) \
                    .get_image()
                frame_msg.update_payload(image)
                frame_msg.history = pred_msg.history
            frame_msg.record_exit(self.component_name, self.logger)
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

    def does_routine_use_queue(self, queue):
        return self.in_queue == queue or self.out_queue == queue
