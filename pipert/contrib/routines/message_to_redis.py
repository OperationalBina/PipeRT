from urllib.parse import urlparse

from pipert.core import QueueHandler
from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_encode, FramePayload
from pipert.core.routine import Routine, RoutineTypes
import os


# TODO: add Error handling to connection

class MessageToRedis(Routine):
    routine_type = RoutineTypes.OUTPUT

    def __init__(self, out_key, queue, maxlen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = out_key
        self.url = urlparse(os.environ.get('REDIS_URL', "redis://127.0.0.1:6379"))
        self.q_handler = QueueHandler(queue)
        self.maxlen = maxlen
        self.msg_handler = None

    def main_logic(self, *args, **kwargs):
        msg = self.q_handler.non_blocking_get()
        if msg:
            msg.record_exit(self.component_name, self.logger)
            if self.use_memory and isinstance(msg.payload, FramePayload):
                encoded_msg = message_encode(msg,
                                             generator=self.generator)
            else:
                encoded_msg = message_encode(msg)
            self.msg_handler.send(self.out_key, encoded_msg)
            return True
        else:
            return False

    def setup(self, *args, **kwargs):
        self.msg_handler = RedisHandler(self.url, self.maxlen)
        self.msg_handler.connect()

    def cleanup(self, *args, **kwargs):
        self.msg_handler.close()

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "redis_send_key": "String",
            "message_queue": "QueueIn",
            "max_stream_length": "Integer"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.q_handler.q == queue
