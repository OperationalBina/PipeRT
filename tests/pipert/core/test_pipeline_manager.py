from unittest.mock import MagicMock
import pytest

from pipert import BaseComponent
from tests.pipert.core.utils.routines.dummy_routine_with_queue import DummyRoutineWithQueue
from tests.pipert.core.utils.routines.dummy_routine import DummyRoutine
from pipert.core.pipeline_manager import PipelineManager


def return_routine_class_object_by_name(name):
    if name == "DummyRoutineWithQueue":
        return DummyRoutineWithQueue
    elif name == "DummyRoutine":
        return DummyRoutine
    else:
        return None


@pytest.fixture(scope="function")
def pipeline_manager():
    pipeline_manager = PipelineManager()
    pipeline_manager.ROUTINES_FOLDER_PATH = "tests/pipert/core/utils/routines"
    pipeline_manager.COMPONENTS_FOLDER_PATH = "tests/pipert/core/utils/components"
    pipeline_manager._get_routine_class_object_by_type_name = MagicMock(side_effect=return_routine_class_object_by_name)
    return pipeline_manager


@pytest.fixture(scope="function")
def pipeline_manager_with_component(pipeline_manager):
    pipeline_manager.components["comp"] = BaseComponent(component_config={}, start_component=False)
    return pipeline_manager


@pytest.fixture(scope="function")
def pipeline_manager_with_component_and_queue(pipeline_manager_with_component):
    response = pipeline_manager_with_component. \
        create_queue_to_component(component_name="comp", queue_name="queue1")
    assert response["Succeeded"], response["Message"]
    return pipeline_manager_with_component


@pytest.fixture(scope="function")
def pipeline_manager_with_component_and_queue_and_routine(pipeline_manager_with_component_and_queue):
    response = \
        pipeline_manager_with_component_and_queue.add_routine_to_component(
            component_name="comp",
            routine_type_name="DummyRoutineWithQueue",
            queue="queue1",
            name="routine1")
    assert response["Succeeded"], response["Message"]
    return pipeline_manager_with_component_and_queue


def test_add_queue(pipeline_manager_with_component):
    response = pipeline_manager_with_component.create_queue_to_component(component_name="comp", queue_name="queue1")
    assert response["Succeeded"], response["Message"]
    assert "queue1" in pipeline_manager_with_component.components["comp"].queues


def test_add_queue_with_same_name(pipeline_manager_with_component_and_queue):
    response = pipeline_manager_with_component_and_queue. \
        create_queue_to_component(component_name="comp", queue_name="queue1")
    assert not response["Succeeded"], response["Message"]


def test_remove_queue(pipeline_manager_with_component_and_queue):
    response = pipeline_manager_with_component_and_queue. \
        remove_queue_from_component(component_name="comp", queue_name="queue1")
    assert response["Succeeded"], response["Message"]


def test_remove_queue_that_is_used_by_routine(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_queue_from_component(component_name="comp", queue_name="queue1")
    assert not response["Succeeded"], response["Message"]
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_routine_from_component(component_name="comp", routine_name="routine1")
    assert response["Succeeded"], response["Message"]
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_queue_from_component(component_name="comp", queue_name="queue1")
    assert response["Succeeded"], response["Message"]


def test_create_routine(pipeline_manager_with_component_and_queue):
    response = \
        pipeline_manager_with_component_and_queue.add_routine_to_component(
            component_name="comp",
            routine_type_name="DummyRoutineWithQueue",
            queue="queue1",
            name="capture_frame")
    assert response["Succeeded"], response["Message"]

    assert len(pipeline_manager_with_component_and_queue.components["comp"]._routines) == 1


def test_create_routine_with_same_name(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        add_routine_to_component(
            component_name="comp",
            routine_type_name="DummyRoutineWithQueue",
            queue="queue1",
            name="routine1")
    assert not response["Succeeded"], response["Message"]


def test_remove_routine(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_routine_from_component(component_name="comp", routine_name="routine1")
    assert response["Succeeded"], response["Message"]

    assert \
        len(pipeline_manager_with_component_and_queue_and_routine.
            components["comp"]._routines) == 0


def test_remove_routine_does_not_exist(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_routine_from_component(component_name="comp", routine_name="not_exist")
    assert not response["Succeeded"], response["Message"]


def test_run_and_stop_component(pipeline_manager_with_component_and_queue_and_routine):
    assert pipeline_manager_with_component_and_queue_and_routine. \
        components["comp"].stop_event.is_set()
    response = pipeline_manager_with_component_and_queue_and_routine. \
        run_component(component_name="comp")
    assert response["Succeeded"], response["Message"]
    assert not pipeline_manager_with_component_and_queue_and_routine. \
        components["comp"].stop_event.is_set()

    response = pipeline_manager_with_component_and_queue_and_routine. \
        stop_component(component_name="comp")
    assert response["Succeeded"], response["Message"]
    assert pipeline_manager_with_component_and_queue_and_routine. \
        components["comp"].stop_event.is_set()


def test_get_routine_type_object_by_name(pipeline_manager):
    assert pipeline_manager._get_routine_class_object_by_type_name("DummyRoutine") is DummyRoutine
