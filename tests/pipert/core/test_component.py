import pytest

import time
import gevent
import zerorpc
# import signal
# import os
from threading import Thread
from torch.multiprocessing import Process
from pipert.core.component import BaseComponent
# from pipert.core.routine import Routine
from tests.pipert.core.test_routine import DummyRoutine
from pipert.core.errors import RegisteredException


class DummyComponent(BaseComponent):

    def __init__(self, endpoint="tcp://0.0.0.0:4242", *args, **kwargs):
        super().__init__(endpoint, *args, **kwargs)

    @staticmethod
    def add(a, b):
        return a + b


def test_zerorpc():
    comp = DummyComponent()
    gevent.spawn(comp.run)
    client = zerorpc.Client()
    client.connect(comp.endpoint)
    assert client.add(2, 3) == 5
    assert client.stop_run() == 0
    client.close()


def test_register_routine():
    comp = DummyComponent()
    rout = DummyRoutine().as_thread()
    comp.register_routine(rout)

    with pytest.raises(RegisteredException):
        comp.register_routine(rout)
    comp.zrpc.close()


def test_safe_stop():

    def foo():
        print("bar")

    comp = DummyComponent()
    rout1 = DummyRoutine().as_thread()
    comp.register_routine(rout1)
    rout2 = Thread(target=foo)
    comp.register_routine(rout2)
    rout3 = Process(target=foo)
    comp.register_routine(rout3)

    gevent.spawn(comp.run)
    client = zerorpc.Client()
    client.connect(comp.endpoint)
    time.sleep(0.1)
    assert client.stop_run() == 0
    client.close()

