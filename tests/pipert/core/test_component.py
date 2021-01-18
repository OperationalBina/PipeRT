import logging
import time
from threading import Thread

import pytest
from multiprocessing import Process

from pipert.core.metrics_collector import NullCollector
from tests.pipert.core.utils.routines.dummy_routine import DummyRoutine
from tests.pipert.core.utils.component.dummy_component import DummyComponent
from tests.pipert.core.utils.routines.dummy_routine_with_queue import DummyRoutineWithQueue
import os


@pytest.fixture(scope="function")
def component_with_queue():
    comp = DummyComponent({})
    comp.MONITORING_SYSTEMS_FOLDER_PATH = os.getcwd() + "/" + "tests/pipert/core/utils/metrics_collectors"
    comp.name = "Comp1"
    comp.logger = logging.getLogger("test_logs.log")
    assert comp.create_queue("que1", 1)
    return comp


@pytest.fixture(scope="function")
def component_with_queue_and_routine(component_with_queue):
    component_with_queue.register_routine(
        DummyRoutineWithQueue(
            name="rout1",
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


def test_remove_queue(component_with_queue):
    assert component_with_queue.delete_queue("que1")
    assert "que1" not in component_with_queue.queues


def test_create_queue_with_same_name(component_with_queue):
    assert not component_with_queue.create_queue("que1", 2)
    assert "que1" in component_with_queue.queues


def test_remove_queue_used_by_routine(component_with_queue_and_routine):
    assert not component_with_queue_and_routine.delete_queue("que1")


def test_remove_routine(component_with_queue_and_routine):
    assert component_with_queue_and_routine.remove_routine("rout1")
    assert "rout1" not in component_with_queue_and_routine._routines


def test_remove_routine_does_not_exist(component_with_queue_and_routine):
    assert not component_with_queue_and_routine.remove_routine("not_exist")


def test_get_component_configuration(component_with_queue_and_routine):
    EXPECTED_COMPONENT_DICTIONARY = {
        "Comp1": {
            "shared_memory": False,
            "queues": ["que1"],
            "routines": {
                "rout1": {
                    "queue": "que1",
                    "routine_type_name": "DummyRoutineWithQueue",
                }
            },
            "component_type_name": "DummyComponent"
        }
    }
    component_configuration = component_with_queue_and_routine.get_component_configuration()
    assert component_configuration == EXPECTED_COMPONENT_DICTIONARY


def test_get_routine_creation(component_with_queue_and_routine):
    EXPECTED_ROUTINE_DICTIONARY = {
        "name": "rout1",
        "queue": "que1",
        "routine_type_name": "DummyRoutineWithQueue",
    }
    routine_configuration = component_with_queue_and_routine. \
        _get_routine_creation(component_with_queue_and_routine.
                              get_routines()["rout1"])
    assert routine_configuration == EXPECTED_ROUTINE_DICTIONARY


def test_setup_component():
    component = DummyComponent(component_config={})
    component_name = "comp"
    shared_memory = True
    queue_names = ["que1", "que2"]

    component_configuration = {
        component_name: {
            "shared_memory": shared_memory,
            "queues": queue_names,
            "routines": {},
            "component_type_name": "DummyComponent"
        }
    }

    component.setup_component(component_config=component_configuration)
    assert component.name == "comp"
    assert component.use_memory == shared_memory
    assert all(queue_name in component.queues for queue_name in queue_names)
    assert component_configuration == component.get_component_configuration()


def test_set_monitoring_with_bad_name(component_with_queue_and_routine):
    component_with_queue_and_routine.set_monitoring_system({
        "name": "BadName"
    })
    assert isinstance(component_with_queue_and_routine.metrics_collector, NullCollector)


def test_set_monitoring_with_good_params(component_with_queue_and_routine):
    component_with_queue_and_routine.set_monitoring_system({
        "name": "Dummy",
        "parameter": "check"
    })
    assert not isinstance(component_with_queue_and_routine.metrics_collector, NullCollector)

