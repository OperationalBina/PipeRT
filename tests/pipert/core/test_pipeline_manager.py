import pytest

from pipert.core.pipeline_manager import PipelineManager


@pytest.fixture(scope="function")
def pipeline_manager():
    pipeline_manager = PipelineManager(open_zerorpc=False)
    return pipeline_manager


@pytest.fixture(scope="function")
def pipeline_manager_with_component(pipeline_manager):
    response = pipeline_manager.create_component(component_name="comp")
    assert response["Succeeded"], response["Message"]
    return pipeline_manager


@pytest.fixture(scope="function")
def pipeline_manager_with_component_and_queue(pipeline_manager_with_component):
    response = pipeline_manager_with_component. \
        create_queue_to_component(component_name="comp", queue_name="queue1")
    assert response["Succeeded"], response["Message"]
    return pipeline_manager_with_component


@pytest.fixture(scope="function")
def pipeline_manager_with_component_and_queue_and_routine(pipeline_manager_with_component_and_queue):
    response = pipeline_manager_with_component_and_queue.add_routine_to_component(
        component_name="comp",
        routine_type_name="ListenToStream",
        stream_address="0",
        out_queue="queue1",
        fps=30,
        name="routine1")
    assert response["Succeeded"], response["Message"]
    return pipeline_manager_with_component_and_queue


def test_create_component(pipeline_manager):  # cant add with the same name for queue comp and routine
    response = pipeline_manager.create_component(component_name="comp")
    assert response["Succeeded"], response["Message"]
    assert "comp" in pipeline_manager.components


def test_create_component_with_same_name(pipeline_manager_with_component):
    response = pipeline_manager_with_component.create_component(component_name="comp")
    assert not response["Succeeded"], response["Message"]


def test_remove_component(pipeline_manager_with_component):
    response = pipeline_manager_with_component.remove_component(component_name="comp")
    assert response["Succeeded"], response["Message"]
    assert "comp" not in pipeline_manager_with_component.components


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
            routine_type_name="ListenToStream",
            stream_address="0",
            out_queue="queue1",
            fps=30,
            name="capture_frame")
    assert response["Succeeded"], response["Message"]

    assert len(pipeline_manager_with_component_and_queue.components["comp"]._routines) == 1


def test_create_routine_with_same_name(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        add_routine_to_component(
            component_name="comp",
            routine_type_name="ListenToStream",
            stream_address="0",
            out_queue="queue1",
            fps=30,
            name="routine1")
    assert not response["Succeeded"], response["Message"]


def test_remove_routine(pipeline_manager_with_component_and_queue_and_routine):
    response = pipeline_manager_with_component_and_queue_and_routine. \
        remove_routine_from_component(component_name="comp", routine_name="routine1")
    assert response["Succeeded"], response["Message"]

    assert \
        len(pipeline_manager_with_component_and_queue_and_routine.
            components["comp"]._routines) == 0


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


def test_create_components_using_structure(pipeline_manager):
    response = pipeline_manager.setup_components([
        {
            "name": "Stream",
            "queues": ["video"],
            "routines":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "0",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    },
                    {
                        "routine_type_name": "MessageToRedis",
                        "redis_send_key": "cam",
                        "message_queue": "video",
                        "max_stream_length": 10,
                        "name": "upload_redis"
                    }
                ]
        },
        {
            "name": "Display",
            "queues": ["messages"],
            "routines":
                [
                    {
                        "routine_type_name": "MessageFromRedis",
                        "redis_read_key": "cam",
                        "message_queue": "messages",
                        "name": "get_frames"
                    },
                    {
                        "routine_type_name": "DisplayCv2",
                        "frame_queue": "messages",
                        "name": "draw_frames"
                    }
                ]
        },
    ])
    assert response["Succeeded"], response["Message"]


def test_create_components_using_bad_structures(pipeline_manager):
    response = pipeline_manager.setup_components([
        {
            "name": "Stream",
            "queues": ["video"],
            "routiness":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "0",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    }
                ]
        },
    ])
    assert not response["Succeeded"], response["Message"]

    response = pipeline_manager.setup_components([
        {
            "name": "Stream",
            "routines":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "0",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    }
                ]
        },
    ])
    assert not response["Succeeded"], response["Message"]

    response = pipeline_manager.setup_components([
        {
            "queues": ["video"],
            "routines":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "0",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    }
                ]
        },
    ])
    assert not response["Succeeded"], response["Message"]

    response = pipeline_manager.setup_components([
        {
            "name": [],
            "queues": ["video"],
            "routines":
                [
                    {
                        "routine_type_name": "ListenToStream",
                        "stream_address":
                            "0",
                        "out_queue": "video",
                        "fps": 30,
                        "name": "capture_frame"
                    }
                ]
        },
    ])
    assert not response["Succeeded"], response["Message"]
