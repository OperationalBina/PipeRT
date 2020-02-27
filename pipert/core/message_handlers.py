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
    def read_next_msg(self, in_key):
        """
        Reads the following message from the one that was last read,
        if no message read before, reads the last message in the message broker.
        cannot read the same message twice.

        Args:
            in_key: the name of the queue/stream at which the relevant message
            is located.
        """
        pass

    @abstractmethod
    def read_most_recent_msg(self, in_key):
        """
        Reads the latest message in the message broker, cannot read the same message twice.

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
        self.last_msg_id = None
        self.connect()

    def read_next_msg(self, in_key):
        if self.last_msg_id:
            last_msg_id_to_read = self.last_msg_id.split("-")
            last_msg_id_to_read = last_msg_id_to_read[0] + "-" + str(int(last_msg_id_to_read[1]) + 1)
        else:
            return self.receive(in_key)

        redis_msg = self.conn.xrange(in_key, count=1, min=last_msg_id_to_read)
        if not redis_msg:
            return None
        self.last_msg_id = redis_msg[0][0]
        msg = redis_msg[0][1]["msg".encode("utf-8")]
        return msg

    def read_most_recent_msg(self, in_key):
        if self.last_msg_id:
            last_msg_id_to_read = self.last_msg_id.split("-")
            last_msg_id_to_read = last_msg_id_to_read[0] + "-" + str(int(last_msg_id_to_read[1]) + 1)
        else:
            return self.receive(in_key)

        redis_msg = self.conn.xrevrange(in_key, count=1, min=last_msg_id_to_read)
        if not redis_msg:
            return None
        self.last_msg_id = redis_msg[0][0]
        msg = redis_msg[0][1]["msg".encode("utf-8")]
        return msg

    def receive(self, in_key):
        # TODO - refactor to use xread instead of xrevrange
        redis_msg = self.conn.xrevrange(in_key, count=1)
        if not redis_msg:
            return None
        self.last_msg_id = redis_msg[0][0]
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
