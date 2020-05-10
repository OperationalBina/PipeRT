import os
import time
from urllib.parse import urlparse

from pipert.core import QueueHandler
from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_decode
from pipert.core.routine import Routine, RoutineTypes


class MessageFromRedis(Routine):
    routine_type = RoutineTypes.INPUT

    def __init__(self, in_key, queue, most_recent=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key = in_key
        self.url = urlparse(os.environ.get('REDIS_URL', "redis://127.0.0.1:6379"))
        self.q_handler = QueueHandler(queue)
        self.msg_handler = None
        self.most_recent = most_recent
        self.read_method = None
        self.flip = False
        self.negative = False

    def main_logic(self, *args, **kwargs):
        encoded_msg = self.read_method(self.in_key)
        if encoded_msg:
            msg = message_decode(encoded_msg)
            msg.record_entry(self.component_name, self.logger)
            success = self.q_handler.deque_non_blocking_put(msg)
            return success
        else:
            time.sleep(0)
            return None

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url)
        if self.most_recent:
            self.read_method = self.msg_handler.read_most_recent_msg
        else:
            self.read_method = self.msg_handler.read_next_msg
        self.msg_handler.connect()

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "redis_read_key": "String",
            "message_queue": "QueueOut",
            "out_key": "str"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.q_handler.q == queue
