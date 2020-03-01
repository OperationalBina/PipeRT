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
        if no message has been read before,
        then read the last message in the message broker
        cannot read the same message twice.

        Args:
            in_key: the name of the queue/stream at which the relevant message
            is located.
        """
        pass

    @abstractmethod
    def read_most_recent_msg(self, in_key):
        """
        Reads the latest message in the message broker,
        cannot read the same message twice.

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
        return self._read_from_redis_using_method(
            in_key=in_key,
            reading_method=self.conn.xrange,
            name=in_key,
            count=1,
            min=self._add_offset_to_stream_id(self.last_msg_id, 1)
        )

    def read_most_recent_msg(self, in_key):
        return self._read_from_redis_using_method(
            in_key=in_key,
            reading_method=self.conn.xrevrange,
            name=in_key,
            count=1,
            min=
            self._add_offset_to_stream_id(self.last_msg_id, 1)
        )

    def receive(self, in_key):
        self.last_msg_id = "Will be changed"
        return self._read_from_redis_using_method(
            in_key,
            self.conn.xrevrange,
            name=in_key,
            count=1
        )

    def _read_from_redis_using_method(self,
                                      in_key,
                                      reading_method,
                                      **method_args):
        if self.last_msg_id is None:
            return self.receive(in_key)
        redis_msg = reading_method(**method_args)

        if not redis_msg:
            return None
        self.last_msg_id = redis_msg[0][0].decode()
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

    def _add_offset_to_stream_id(self, stream_id, offset):
        if stream_id is None:
            return None
        fixed_id = stream_id.split("-")
        last_msg_id_to_read = '-'.join([fixed_id[0],
                                        str(int(fixed_id[1]) + offset)])
        return last_msg_id_to_read
