import time
from queue import Empty, Full
from urllib.parse import urlparse

from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_decode, message_encode
from pipert.core.routine import Routine


# TODO: add Error handling to connection

class MessageToRedis(Routine):

    def __init__(self, redis_send_key, url, message_queue, max_stream_length, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = redis_send_key
        self.url = urlparse(url)
        self.queue = message_queue
        self.maxlen = max_stream_length
        self.msg_handler = None

    def main_logic(self, *args, **kwargs):
        try:
            msg = self.queue.get(block=False)
            msg.record_exit(self.component_name, self.logger)
            encoded_msg = message_encode(msg)
            self.msg_handler.send(self.out_key, encoded_msg)
            time.sleep(0)
            return True
        except Empty:
            time.sleep(0)  # yield the control of the thread
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
            "url": "String",
            "message_queue": "Queue",
            "max_stream_length": "Integer"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.queue == queue
