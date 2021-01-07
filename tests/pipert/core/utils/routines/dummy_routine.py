import logging

from pipert.core.routine import Routine, Events
from tests.pipert.core.test_routine import dummy_before_stop_handler

class DummyRoutine(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        return False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _setup_logger(self):
        self.logger = logging.getLogger("test_logs.log")

    def main_logic(self, *args, **kwargs):
        self.metrics_collector.collect_latency(0.1, self.component_name)
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass

    def _extension_dummy(self):
        self.add_event_handler(Events.AFTER_LOGIC,
                               dummy_before_stop_handler,
                               first=True)
