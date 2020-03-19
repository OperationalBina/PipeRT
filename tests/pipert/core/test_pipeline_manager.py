import pytest

from pipert.core.pipeline_manager import PipelineManager


@pytest.fixture(scope="function")
def pipeline_manager():
    pipeline_manager = PipelineManager(open_zerorpc=False)
    return pipeline_manager


def test_create_component(pipeline_manager):
    assert pipeline_manager.create_component("comp1")["Succeeded"]
    assert "comp1" in pipeline_manager.components
