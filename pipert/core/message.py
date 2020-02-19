import collections
from abc import ABC, abstractmethod

import numpy as np
import time
import pickle
import cv2


class Payload(ABC):

    def __init__(self, data):
        self.data = data
        self.encoded = False
        pass

    @abstractmethod
    def decode(self):
        pass

    @abstractmethod
    def encode(self):
        pass

    @abstractmethod
    def is_empty(self):
        pass


class FramePayload(Payload):

    def __init__(self, data):
        super().__init__(data)

    def decode(self):
        decoded_img = cv2.imdecode(np.fromstring(self.data, dtype=np.uint8),
                                   cv2.IMREAD_COLOR)
        self.data = decoded_img
        self.encoded = False

    def encode(self):
        buf = cv2.imencode('.jpeg', self.data)[1].tobytes()
        self.data = buf
        self.encoded = True

    def is_empty(self):
        if not self.data:
            return True
        else:
            return False


class PredictionPayload(Payload):
    def __init__(self, data):
        super().__init__(data)

    def decode(self):
        pass

    def encode(self):
        pass

    def is_empty(self):
        if not self.data.has("pred_boxes") or not self.data.pred_boxes:
            return True
        else:
            return False


class Message:
    counter = 0

    def __init__(self, data, source_address):
        if isinstance(data, np.ndarray):
            self.payload = FramePayload(data)
        else:
            self.payload = PredictionPayload(data)
        self.source_address = source_address
        self.history = collections.defaultdict(dict)
        self.id = f"{self.source_address}_{Message.counter}"
        Message.counter += 1

    def update_payload(self, data):
        if self.payload.encoded:
            self.payload.decode()
        self.payload.data = data

    def get_payload(self):
        if self.payload.encoded:
            self.payload.decode()
        return self.payload.data

    def is_empty(self):
        return self.payload.is_empty()

    # component name should represent a unique instance of the component
    def record_entry(self, component_name, logger):
        """Records the timestamp of the message's entry into a component.

        Args:
            component_name: the name of the component that the message entered.
            logger: the logger object of the component's input routine.
        """
        self.history[component_name]["entry"] = time.time()
        logger.info("Received the following message: %s", str(self))

    def record_custom(self, component_name, section):
        """Records the timestamp of the message's entry into some section
        of a component.

        Args:
            component_name: the name of the component that the message is in.
            section: the name of the section within the component that the
            message entered.
        """
        self.history[component_name][section] = time.time()

    def record_exit(self, component_name, logger):
        """Records the timestamp of the message's exit out of a component.

        Args:
            component_name: the name of the component that the message exited.
            logger: the logger object of the component's output routine.
        """
        self.history[component_name]["exit"] = time.time()
        logger.info("Sending the following message: %s", str(self))

    def get_latency(self, component_name):
        """Returns the time it took for a message to pass through a whole
        component.

        Using the message's history, this method calculates and returns the
        amount of time that passed from the moment the message entered a
        component, to the moment that it left it.
        Args:
            component_name: the name of the relevant component.
        """
        if component_name in self.history and \
                'entry' in self.history[component_name] and \
                'exit' in self.history[component_name]:
            return self.history[component_name]['exit'] - \
                self.history[component_name]['entry']
        else:
            return None

    def __str__(self):
        return f"{{msg id: {self.id}, " \
               f"payload type: {type(self.payload)}, " \
               f"source address: {self.source_address} }}\n"

    def full_description(self):
        return f"msg id: {self.id}, " \
               f"payload type: {type(self.payload)}, " \
               f"source address: {self.source_address}, " \
               f"history: {self.history} \n"


def message_encode(msg):
    """Encodes the message object.

    This method compresses the message payload and then serializes the whole
    message object into bytes, using pickle.

    Args:
        msg: the message to encode.
    """
    msg.payload.encode()
    return pickle.dumps(msg)


# if lazy=True, then the payload data will only be decoded once it's accessed
def message_decode(encoded_msg, lazy=False):
    """Decodes the message object.

    This method deserializes the pickled message, and decodes the message
    payload if 'lazy' is False.

    Args:
        encoded_msg: the message to decode.
        lazy: if this is True, then the payload will only be decoded once it's
        accessed.
    """
    msg = pickle.loads(encoded_msg)
    if not lazy:
        msg.payload.decode()
    return msg
