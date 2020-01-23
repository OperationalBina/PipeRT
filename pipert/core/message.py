from abc import ABC, abstractmethod
from io import BytesIO

import numpy as np
import time
import pickle
import cv2

from PIL import Image


class Payload(ABC):

    def __init__(self, data):
        self.data = data
        pass

    @abstractmethod
    def decode(self):
        pass

    @abstractmethod
    def encode(self):
        pass


class FramePayload(Payload):

    def __init__(self, data):
        super().__init__(data)

    def decode(self):
        self.data = np.array(Image.open(BytesIO(self.data)))

    def encode(self):
        _, buf = cv2.imencode(".jpg", self.data)
        self.data = buf.tobytes()


class PredictionPayload(Payload):
    def __init__(self, data):
        super().__init__(data)

    def decode(self):
        pass

    def encode(self):
        pass


class Message:
    next_msg_id = 0

    def __init__(self, data, stream_address):
        if isinstance(data, np.ndarray):
            self.payload = FramePayload(data)
        else:
            self.payload = PredictionPayload(data)
        self.stream_address = stream_address
        self.history = {}
        self.id = Message.next_msg_id
        Message.next_msg_id += 1

    def update_payload(self, data):
        self.payload.data = data

    # component_name should also contain an ID for that component, in case there are multiple instances
    def record_entry(self, component_name):
        self.history[component_name] = [time.time(), None]

    def record_exit(self, component_name):
        if component_name in self.history:
            self.history[component_name][1] = time.time()
        else:
            self.history[component_name] = [None, time.time()]

    def get_latency(self, component_name):
        if not (component_name in self.history and self.history[component_name][1]):
            return None
        return self.history[component_name][1] - self.history[component_name][0]

    def __str__(self):
        return "msg id: {}, payload type: {}, stream address: {}, history: {} \n".format(self.id,
                                                                                         type(self.payload),
                                                                                         self.stream_address,
                                                                                         self.history)


def message_encode(msg):
    msg.payload.encode()
    return pickle.dumps(msg)


def message_decode(encoded_msg):
    msg = pickle.loads(encoded_msg)
    msg.payload.decode()
    return msg
