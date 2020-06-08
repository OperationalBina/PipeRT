import time
from pipert import Routine
from pipert.core import Message
from pipert.core.routine import RoutineTypes
from queue import Empty


class AnomalyLogic(Routine):
    routine_type = RoutineTypes.PROCESSING

    def __init__(self, in_queue, out_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_queue = in_queue
        self.out_queue = out_queue

    def main_logic(self, *args, **kwargs):
        try:
            frame_msg = self.in_queue.get(block=False)
            frame = frame_msg.get_payload()

            # TODO: implement Yonatan's model logic
            # need to rount to 2 digits after point.
            # need to turn to string

            try:
                self.out_queue.get(block=False)
                self.state.dropped += 1
            except Empty:
                pass
            pred_msg = Message(pred, frame_msg.source_address)
            self.out_queue.put(pred_msg, block=False)

            return True

        except Empty:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.state.dropped = 0

    def cleanup(self, *args, **kwargs):
        # del self.model, self.device, self.classes, self.colors
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