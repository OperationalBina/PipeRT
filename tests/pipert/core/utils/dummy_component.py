from pipert.core.component import BaseComponent


class DummyComponent(BaseComponent):

    def __init__(self, component_config, start_component=False):
        super().__init__(component_config, start_component=start_component)

    @staticmethod
    def add(a, b):
        return a + b
