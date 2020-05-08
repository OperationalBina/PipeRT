import os
from urllib.parse import urlparse

from pipert.core.routine import Routine, RoutineTypes
from pipert.core import QueueHandler
from pipert.core.message import message_decode
from pipert.core.message_handlers import RedisHandler
import time


class MetaAndFrameFromRedis(Routine):
    routine_type = RoutineTypes.INPUT

    def __init__(self, redis_read_meta_key, redis_read_image_key, image_meta_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis_read_meta_key = redis_read_meta_key
        self.redis_read_image_key = redis_read_image_key
        self.url = urlparse(os.environ.get('REDIS_URL', "redis://127.0.0.1:6379"))
        self.image_meta_queue = QueueHandler(image_meta_queue)
        self.msg_handler = None
        self.flip = False
        self.negative = False

    def receive_msg(self, in_key, most_recent=True):
        if most_recent:
            encoded_msg = self.msg_handler.read_most_recent_msg(in_key)
        else:
            encoded_msg = self.msg_handler.receive(in_key)
        if not encoded_msg:
            return None
        msg = message_decode(encoded_msg)
        msg.record_entry(self.component_name, self.logger)
        return msg

    def main_logic(self, *args, **kwargs):
        pred_msg = self.receive_msg(self.redis_read_meta_key, most_recent=True)
        frame_msg = self.receive_msg(self.redis_read_image_key, most_recent=False)
        print(f"Meta&Frame GOT:\nFrame: {frame_msg}\nMeta: {pred_msg}")
        if frame_msg:

            self.image_meta_queue.deque_non_blocking_put((frame_msg, pred_msg))
            print(f"Meta&Frame PUT:\nFrame: {frame_msg}\nMeta: {pred_msg}")
            return True

        else:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url)

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "redis_read_meta_key": "String",
            "redis_read_image_key": "String",
            "image_meta_queue": "QueueOut",
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.image_meta_queue == queue
