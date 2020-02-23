import logging

import pytest

import time
import numpy as np
# import signal
# import os
from threading import Thread
from torch.multiprocessing import Process
from pipert.core.component import BaseComponent
# from pipert.core.routine import Routine
from pipert.core.message import Message, FramePayload, message_encode, \
    message_decode


class DummyMessage(Message):

    def __init__(self, data, stream_address, *args, **kwargs):
        super().__init__(data, stream_address)


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

