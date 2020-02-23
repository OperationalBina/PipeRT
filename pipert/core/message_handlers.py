from abc import ABC, abstractmethod
import redis


class MessageHandler(ABC):

    @abstractmethod
    def receive(self, in_key):
        """
        Receives the latest message from the message broker.

        Args:
            in_key: the name of the queue/stream at which the relevant message
            is located.
        """
        pass

    @abstractmethod
    def send(self, out_key, msg):
        """
        Sends a message to the message broker.

        Args:
            out_key: the name of the queue/stream at which the relevant message
            will be placed.
            msg: the message object that is being sent.
        """
        pass

    @abstractmethod
    def connect(self):
        """
        Establishes a connection to the message broker.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Closes the connection to the message broker.
        """
        pass


class RedisHandler(MessageHandler):

    def __init__(self, url, maxlen=100):
        self.conn = None
        self.url = url
        self.maxlen = maxlen
        self.connect()

    def receive(self, in_key):
        # TODO - refactor to use xread instead of xrevrange
        redis_msg = self.conn.xrevrange(in_key, count=1)
        if not redis_msg:
            return None
        msg = redis_msg[0][1]["msg".encode("utf-8")]
        return msg

    def send(self, msg, out_key):
        fields = {
            "msg": msg
        }
        _ = self.conn.xadd(out_key, fields, maxlen=self.maxlen)

    def connect(self):
        self.conn = redis.Redis(host=self.url.hostname, port=self.url.port)
        if not self.conn.ping():
            raise Exception('Redis unavailable')

    def close(self):
        self.conn.close()
