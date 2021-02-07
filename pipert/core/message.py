import collections
from abc import ABC, abstractmethod

import sys
if sys.version_info.minor >= 8:
    from pipert.core.multiprocessing_shared_memory import get_shared_memory_object

import numpy as np
import time
import pickle


class Payload(ABC):

    def __init__(self, data):
        self.data = data
        self.encoded = False
        pass

    @abstractmethod
    def decode(self):
        pass

    @abstractmethod
    def encode(self, generator):
        pass

    @abstractmethod
    def is_empty(self):
        pass


class FramePayload(Payload):

    def __init__(self, data):
        super().__init__(data)
        self.shape = None
        self.dtype = None
        self.generator = None
        self.frame_size = 0

    def decode(self):
        if self.encoded:
            if isinstance(self.data, str):
                decoded_img = self._get_frame()
            else:
                decoded_img = np.frombuffer(self.data, dtype=self.dtype)
                decoded_img = decoded_img.reshape(self.shape)
            self.data = decoded_img
            self.encoded = False

    def encode(self, generator):
        if not self.encoded:
            self.shape = self.data.shape
            self.dtype = self.data.dtype
            buf = self.data.tobytes()
            if generator is None:
                self.data = buf
            else:
                if sys.version_info.minor >= 8:
                    memory = generator.get_next_shared_memory(size=len(buf))
                    memory.buf[:] = bytes(buf)
                    self.data = memory.name
                else:
                    self.frame_size = len(buf)
                    memory_name = generator.get_next_shared_memory_name()
                    memory = generator.get_shared_memory_object(memory_name)
                    memory.acquire_semaphore()
                    memory.write_to_memory(buf)
                    memory.release_semaphore()
                    self.generator = generator
                    self.data = memory_name
            self.encoded = True

    def is_empty(self):
        return self.data is None

    def _get_frame(self):
        if sys.version_info.minor >= 8:
            memory = get_shared_memory_object(self.data)
        else:
            if self.generator is not None:
                memory = self.generator.get_shared_memory_object(self.data)
            else:
                memory = None
        if memory:
            if sys.version_info.minor >= 8:
                data = bytes(memory.buf)
                memory.close()
            else:
                memory.acquire_semaphore()
                data = memory.read_from_memory(self.frame_size)
                memory.release_semaphore()
            frame = np.frombuffer(data, dtype=self.dtype)
            return frame.reshape(self.shape)
        return None


class PredictionPayload(Payload):
    def __init__(self, data):
        super().__init__(data)

    def decode(self):
        pass

    def encode(self, generator):
        pass

    def is_empty(self):
        if not self.data.has("pred_boxes") or not self.data.pred_boxes:
            return True
        else:
            return False


class FrameMetadataPayload(Payload):

    def __init__(self, data):
        super().__init__(data)
        self.shape = None
        self.dtype = None
        self.generator = None
        self.frame_size = 0

    def decode(self):
        if self.encoded:
            if isinstance(self.data[0], str):
                decoded_img = self._get_frame()
            else:
                decoded_img = np.frombuffer(self.data[0], dtype=self.dtype)
                decoded_img = decoded_img.reshape(self.shape)
            self.data = (decoded_img, self.data[1])
            self.encoded = False

    def encode(self, generator):
        if not self.encoded:
            self.shape = self.data[0].shape
            self.dtype = self.data[0].dtype
            buf = self.data[0].tobytes()
            if generator is None:
                self.data = (buf, self.data[1])
            else:
                if sys.version_info.minor >= 8:
                    memory = generator.get_next_shared_memory(size=len(buf))
                    memory.buf[:] = bytes(buf)
                    self.data = (memory.name, self.data[1])
                else:
                    self.frame_size = len(buf)
                    memory_name = generator.get_next_shared_memory_name()
                    memory = generator.get_shared_memory_object(memory_name)
                    memory.acquire_semaphore()
                    memory.write_to_memory(buf)
                    memory.release_semaphore()
                    self.generator = generator
                    self.data = (memory_name, self.data[1])
            self.encoded = True

    def is_empty(self):
        return self.data is None

    def _get_frame(self):
        if sys.version_info.minor >= 8:
            memory = get_shared_memory_object(self.data[0])
        else:
            if self.generator is not None:
                memory = self.generator.get_shared_memory_object(self.data[0])
            else:
                memory = None
        if memory:
            if sys.version_info.minor >= 8:
                data = bytes(memory.buf)
                memory.close()
            else:
                memory.acquire_semaphore()
                data = memory.read_from_memory(self.frame_size)
                memory.release_semaphore()
            frame = np.frombuffer(data, dtype=self.dtype)
            return frame.reshape(self.shape)
        return None


class Message:
    counter = 0

    def __init__(self, data, source_address):
        if isinstance(data, np.ndarray):
            self.payload = FramePayload(data)
        elif isinstance(data, tuple):
            self.payload = FrameMetadataPayload(data)
        else:
            self.payload = PredictionPayload(data)
        self.source_address = source_address
        self.history = collections.defaultdict(dict)  # TODO: Maybe use OrderedDict?
        self.reached_exit = False
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
        """
        Records the timestamp of the message's entry into a component.

        Args:
            component_name: the name of the component that the message entered.
            logger: the logger object of the component's input routine.
        """
        self.history[component_name]["entry"] = time.time()
        logger.debug("Received the following message: %s", str(self))

    def record_custom(self, component_name, section):
        """
        Records the timestamp of the message's entry into some section
        of a component.

        Args:
            component_name: the name of the component that the message is in.
            section: the name of the section within the component that the
            message entered.
        """
        self.history[component_name][section] = time.time()

    def record_exit(self, component_name, logger):
        """
        Records the timestamp of the message's exit out of a component.
        Additionally, it enables a flag called 'reached_exit' if the message is exiting
        the pipeline's "output component".

        Args:
            component_name: the name of the component that the message exited.
            logger: the logger object of the component's output routine.
        """
        if "exit" not in self.history[component_name]:
            self.history[component_name]["exit"] = time.time()
            if component_name == "FlaskVideoDisplay" or component_name == "VideoWriter":
                logger.debug("The following message has reached the exit: %s", str(self))
                self.reached_exit = True
            else:
                logger.debug("Sending the following message: %s", str(self))

    def get_latency(self, component_name):
        """
        Returns the time it took for a message to pass through a whole
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

    def get_end_to_end_latency(self, output_component):
        """
        Returns the time it took for a message to pass through the pipeline.

        Args:
            output_component: the name of the pipeline's output component.
        """
        if output_component in self.history and self.reached_exit:
            try:
                return self.history[output_component]['exit'] - self.history['VideoCapture']['entry']
            except KeyError:
                return None
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


def message_encode(msg, generator=None):
    """
    Encodes the message object.

    This method compresses the message payload and then serializes the whole
    message object into bytes, using pickle.

    Args:
        msg: the message to encode.
        generator: generator necessary for shared memory usage.
    """
    msg.payload.encode(generator)
    return pickle.dumps(msg)


def message_decode(encoded_msg, lazy=False):
    """
    Decodes the message object.

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
