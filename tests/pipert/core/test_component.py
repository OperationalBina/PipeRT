import pytest

import time
# import signal
# import os
from threading import Thread
from torch.multiprocessing import Process
from pipert.core.component import BaseComponent
# from pipert.core.routine import Routine
from tests.pipert.core.test_routine import DummyRoutine


class DummyComponent(BaseComponent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def add(a, b):
        return a + b


def test_register_routine():
    comp = DummyComponent()
    rout = DummyRoutine().as_thread()
    comp.register_routine(rout)

    assert rout in comp._routines
    assert rout.stop_event == comp.stop_event


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

    comp.run()
    time.sleep(0.1)
    assert comp.stop_run() == 0
