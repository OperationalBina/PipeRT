from pipert.core.component import BaseComponent


class DummyComponent(BaseComponent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def add(a, b):
        return a + b
