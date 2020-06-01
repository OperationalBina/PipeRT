import time
from threading import Thread

import pytest
from torch.multiprocessing import Process
from tests.pipert.core.utils.dummy_routine import DummyRoutine
from tests.pipert.core.utils.dummy_component import DummyComponent
from tests.pipert.core.utils.dummy_routine_with_queue import DummyRoutineWithQueue


@pytest.fixture(scope="function")
def component_with_queue():
    comp = DummyComponent({})
    assert comp.create_queue("que1", 1)
    return comp

@pytest.fixture(scope="function")
def component_with_queue_and_routine(component_with_queue):
    component_with_queue.register_routine(
        DummyRoutineWithQueue(
            queue=component_with_queue.queues["que1"])
        .as_thread())
    return component_with_queue

def test_register_routine():
    comp = DummyComponent({})
    rout = DummyRoutine().as_thread()
    comp.register_routine(rout)

    assert rout in comp._routines.values()
    assert rout.stop_event == comp.stop_event


def test_safe_stop():

    def foo():
        print("bar")

    comp = DummyComponent({})
    rout1 = DummyRoutine().as_thread()
    comp.register_routine(rout1)
    rout2 = Thread(target=foo)
    comp.register_routine(rout2)
    rout3 = Process(target=foo)
    comp.register_routine(rout3)

    comp.run_comp()
    time.sleep(0.1)
    assert comp.stop_run() == 0


def test_create_queue():
    comp = DummyComponent({})
    assert comp.create_queue("que1", 1)
    assert "que1" in comp.queues


def test_create_queue_with_same_name(component_with_queue):
    assert not component_with_queue.create_queue("que1", 2)
    assert "que1" in component_with_queue.queues


def test_remove_queue_used_by_routine(component_with_queue_and_routine):
    assert not component_with_queue_and_routine.delete_queue("que1")
