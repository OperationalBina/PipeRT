import pytest

from pipert.core.pipeline_manager import PipelineManager


@pytest.fixture(scope="function")
def pipeline_manager():
    pipeline_manager = PipelineManager(open_zerorpc=False)
    return pipeline_manager


def test_create_component(pipeline_manager):  # cant add with the same name for queue comp and routine
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert "comp1" in pipeline_manager.components


def test_create_component_with_same_name(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert not pipeline_manager.create_component("comp1")["Succeeded"]


def test_add_queue(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert pipeline_manager.create_queue_to_component("comp1", "que1")["Succeeded"]
    assert "que1" in pipeline_manager.components["comp1"].queues


def test_add_queue_with_same_name(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert pipeline_manager.create_queue_to_component("comp1", "que1")["Succeeded"]
    assert not pipeline_manager.create_queue_to_component("comp1", "que1")["Succeeded"]


def test_create_routine(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert pipeline_manager.create_queue_to_component("comp1", "que1")["Succeeded"]
    assert pipeline_manager.add_routine_to_component(
        component_name="comp1",
        routine_type_name="ListenToStream",
        stream_address="/home/internet/Desktop/video.mp4",
        out_queue="que1",
        fps=30,
        name="capture_frame")["Succeeded"]

    assert len(pipeline_manager.components["comp1"]._routines) == 1


def test_create_routine_with_same_name(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert pipeline_manager.create_queue_to_component("comp1", "que1")["Succeeded"]
    assert pipeline_manager.add_routine_to_component(
        component_name="comp1",
        routine_type_name="ListenToStream",
        stream_address="/home/internet/Desktop/video.mp4",
        out_queue="que1",
        fps=30,
        name="capture_frame")["Succeeded"]

    assert not pipeline_manager.add_routine_to_component(
        component_name="comp1",
        routine_type_name="ListenToStream",
        stream_address="/home/internet/Desktop/video.mp4",
        out_queue="que1",
        fps=30,
        name="capture_frame")["Succeeded"]
