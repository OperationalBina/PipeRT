import logging
import time
import numpy as np
import sys
if sys.version_info.minor == 8:
    from pipert.core.multiprocessing_shared_memory import MpSharedMemoryGenerator as smGen
else:
    from pipert.core.shared_memory import SharedMemoryGenerator as smGen
from pipert.core.message import Message, FramePayload, message_encode, \
    message_decode, PredictionPayload, FrameMetadataPayload


class DummyMessage(Message):

    def __init__(self, data, stream_address, *args, **kwargs):
        super().__init__(data, stream_address)


class DummyGenerator(smGen):
    def __init__(self):
        super().__init__("Dummy_generator")


def create_msg():
    img = np.random.rand(576, 720, 3)
    msg = DummyMessage(img, "localhost")
    return msg


def test_get_payload():
    img = np.random.rand(576, 720, 3)
    msg = DummyMessage(img, "localhost")
    assert isinstance(msg.payload, FramePayload)
    assert (msg.get_payload() == img).all()


def test_update_payload():
    msg = create_msg()
    new_img = np.random.rand(576, 720, 3)
    msg.update_payload(new_img)
    assert (msg.get_payload() == new_img).all()


def test_message_encode():
    msg = create_msg()
    encoded_msg = message_encode(msg)
    decoded_msg = message_decode(encoded_msg)
    assert msg.id == decoded_msg.id
    assert msg.source_address == decoded_msg.source_address
    assert msg.history == decoded_msg.history


def test_get_latency():
    msg = create_msg()
    logger = logging.getLogger('test')
    logger.addHandler(logging.NullHandler())
    msg.record_entry("test", logger)
    time.sleep(1)
    msg.record_exit("test", logger)
    assert round(msg.get_latency("test")) == 1


def test_get_end_to_end_latency():
    msg = create_msg()
    logger = logging.getLogger('vidcap')
    logger.addHandler(logging.NullHandler())
    msg.record_entry("VideoCapture", logger)
    assert msg.get_latency("VideoCapture") is None
    msg.record_exit("VideoCapture", logger)
    assert msg.get_end_to_end_latency("FlaskVideoDisplay") is None
    msg.record_entry("FlaskVideoDisplay", logger)
    msg.record_exit("FlaskVideoDisplay", logger)
    assert msg.reached_exit
    latency = msg.get_end_to_end_latency("FlaskVideoDisplay")
    assert latency is not None
    assert not msg.is_empty()


def test_message_encode_shared_memory():
    generator = DummyGenerator()
    msg = create_msg()
    encoded_msg = message_encode(msg, generator)
    decoded_msg = message_decode(encoded_msg)
    assert msg.id == decoded_msg.id
    assert msg.source_address == decoded_msg.source_address
    assert msg.history == decoded_msg.history
    generator.cleanup()


def test_frame_metadata_payload_decode_encode():
    metadata_dictionary = {"id": 2}
    img = np.random.rand(576, 720, 3)

    msg = Message((img, metadata_dictionary.copy()), "localhost")
    assert isinstance(msg.payload, FrameMetadataPayload)
    encoded_message = message_encode(msg)
    decoded_message = message_decode(encoded_message)
    decoded_message_data = decoded_message.get_payload()
    assert decoded_message_data[1] == metadata_dictionary
    # assert (decoded_message_data[0] == img).all()


def test_prediction_payload_decode_encode():
    preds = {"test": 1}

    msg = Message(preds.copy(), "localhost")
    assert isinstance(msg.payload, PredictionPayload)
    encoded_message = message_encode(msg)
    decoded_message = message_decode(encoded_message)
    decoded_message_data = decoded_message.get_payload()
    assert preds == decoded_message_data
