import cv2
from pipert.core.routine import Routine, RoutineTypes
from queue import Empty, Full
import time


class VisLogicAnomaly(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue

    def main_logic(self, *args, **kwargs):
        # TODO implement input that takes both frame and metadata
        try:
            frame_msg, pred_msg = self.in_queue.get(block=False)
            # print("frame", frame_msg)
            # print("pred", pred_msg)
            if pred_msg is not None and not pred_msg.is_empty():
                frame = frame_msg.get_payload()
                pred = pred_msg.get_payload()
                image = self.draw_pred_on_frame(frame, pred)
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

    def draw_pred_on_frame(self, frame, prediction):
        font = cv2.FONT_HERSHEY_SIMPLEX
        org = (50, 50)
        fontScale = 1
        color = (255, 0, 0)
        thickness = 2
        image = cv2.putText(frame, prediction, org, font, fontScale, color, thickness, cv2.LINE_AA)
        return image

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        pass

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "in_queue": "QueueIn",
            "out_queue": "QueueOut",
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return (self.in_queue == queue) or (self.out_queue == queue)
