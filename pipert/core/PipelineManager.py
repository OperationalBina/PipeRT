import zerorpc
from pipert.core.component import BaseComponent


class PipelineManager:

    def __init__(self, endpoint="tcp://0.0.0.0:0001"):
        """
        Args:
            endpoint: the endpoint the PipelineManager's zerorpc server will listen
            in.
        """
        super().__init__()
        self.components = {}
        self.endpoint_port_counter = 2
        self.zrpc = zerorpc.Server(self)
        self.zrpc.bind(endpoint)

    def create_component(self, component_name):
        pass

    def remove_component(self, component_name):
        pass

    def add_routine_to_component(self, component_name, routine_name, **routine_kwargs):
        pass

    def remove_routine_from_component(self, component_name, routine_name):
        pass

    def create_queue_to_component(self, component_name, queue_name):
        pass

    def remove_queue_from_component(self, component_name, queue_name):
        pass

    def run_component(self, component_name):
        pass

    def stop_component(self, component_name):
        pass

    def run_all_components(self):
        pass

    def stop_all_components(self):
        pass

    def get_all_routines(self):
        pass

    def get_routine_information(self):
        pass

    def _get_routine_object_by_name(self, routine_name):
        pass
