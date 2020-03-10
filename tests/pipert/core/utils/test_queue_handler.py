from pipert.core.utlis import QueueHandler
from queue import Queue
import pytest
import time


@pytest.fixture
def q_handler() -> QueueHandler:
    q = Queue(maxsize=1)
    yield QueueHandler(q)


def test_put(q_handler):
    q_handler.put(1)
    assert q_handler.q.full()


def test_get(q_handler):
    q_handler.put(1)
    assert q_handler.get() == 1


def test_timeout_get(q_handler):
    start = time.time()
    assert q_handler.timeout_get(0.1) is None
    assert time.time() - start > 0.1
    q_handler.put(1)
    assert q_handler.timeout_get(0.1) == 1


def test_non_blocking_get(q_handler):
    assert q_handler.non_blocking_get() is None
    q_handler.put(1)
    assert q_handler.non_blocking_get() == 1


def test_timeout_put(q_handler):
    start = time.time()
    assert q_handler.timeout_put(1, 0.1)
    assert time.time() - start < 0.1
    start = time.time()
    assert not q_handler.timeout_put(1, 0.1)
    assert time.time() - start > 0.1
    assert q_handler.get() == 1


def test_non_blocking_put(q_handler):
    q_handler.non_blocking_put(1)
    assert not q_handler.non_blocking_put(1)
    assert q_handler.get() == 1


def test_deque_timeout_put(q_handler):
    start = time.time()
    assert q_handler.deque_timeout_put(1, 0.1)
    assert time.time() - start < 0.1
    start = time.time()
    assert not q_handler.deque_timeout_put(2, 0.1)
    assert time.time() - start > 0.1
    assert q_handler.get() == 2


def test_deque_non_blocking_put(q_handler):
    assert q_handler.deque_non_blocking_put(1)
    assert not q_handler.deque_non_blocking_put(2)
    assert q_handler.get() == 2
