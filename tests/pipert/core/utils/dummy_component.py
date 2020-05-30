from pipert.core.component import BaseComponent


class DummyComponent(BaseComponent):

    def __init__(self, component_config):
        super().__init__(component_config)

    @staticmethod
    def add(a, b):
        return a + b
