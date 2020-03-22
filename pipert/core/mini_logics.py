import time
from pipert.core.message_handlers import RedisHandler
from pipert.core.message import message_decode, message_encode, FramePayload
from pipert.core.routine import Routine
from pipert.core import QueueHandler


# TODO: add Error handling to connection
class Message2Redis(Routine):

    def __init__(self, out_key, url, queue, maxlen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_key = out_key
        self.url = url
        self.q_handler = QueueHandler(queue)
        self.maxlen = maxlen
        self.msg_handler = None

    def main_logic(self, *args, **kwargs):
        msg = self.q_handler.non_blocking_get()
        if msg:
            msg.record_exit(self.component_name, self.logger)
            if self.use_memory and isinstance(msg.payload, FramePayload):
                encoded_msg = message_encode(msg,
                                             generator=self.memory_generator)
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


class MessageFromRedis(Routine):

    def __init__(self, in_key, url, queue, most_recent=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_key = in_key
        self.url = url
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
