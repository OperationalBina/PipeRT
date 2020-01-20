import pytest

import time
import gevent
import zerorpc

from pipert.core.component import BaseComponent
from pipert.core.routine import Routine


class DummyComponent(BaseComponent):

    def __init__(self, endpoint="tcp://0.0.0.0:4242", *args, **kwargs):
        super().__init__(endpoint, *args, **kwargs)


def test_zerorpc():
    comp = DummyComponent()
    gevent.spawn(comp.run)
    client = zerorpc.Client()
    client.connect(comp.endpoint)
    result = client.stop_run()
    assert result == 0
    assert result != 1


def test_register_routine():
    pass
