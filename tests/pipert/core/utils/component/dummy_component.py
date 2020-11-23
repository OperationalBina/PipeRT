from pipert.core.component import BaseComponent
import logging


class DummyComponent(BaseComponent):

    def __init__(self, component_config, start_component=False):
        super().__init__(component_config, start_component=start_component)

    def _setup_logger(self):
        self.logger = logging.getLogger("test_logs.log")

    @staticmethod
    def add(a, b):
        return a + b
