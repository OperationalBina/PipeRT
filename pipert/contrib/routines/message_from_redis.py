import os
import time
from queue import Empty, Full
from urllib.parse import urlparse

from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_decode
from pipert.core.routine import Routine, RoutineTypes


class MessageFromRedis(Routine):
    routine_type = RoutineTypes.INPUT

    def __init__(self, redis_read_key, message_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key = redis_read_key
        # self.url = urlparse(os.environ.get('REDIS_URL'))
        self.url = urlparse("redis://127.0.0.1:6379")
        self.queue = message_queue
        self.msg_handler = None
        self.flip = False
        self.negative = False

    def main_logic(self, *args, **kwargs):
        encoded_msg = self.msg_handler.read_most_recent_msg(self.in_key)
        if encoded_msg:
            msg = message_decode(encoded_msg)
            msg.record_entry(self.component_name, self.logger)
            try:
                self.queue.put(msg, block=False)
                return True
            except Full:
                try:
                    self.queue.get(block=False)
                except Empty:
                    pass
                finally:
                    self.queue.put(msg, block=False)
                    return True
        else:
            time.sleep(0)
            return False

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url)
        self.msg_handler.connect()

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "redis_read_key": "String",
            "message_queue": "Queue"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.queue == queue
