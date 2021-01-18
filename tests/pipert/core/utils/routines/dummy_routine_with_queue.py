import logging

from pipert.core.routine import Routine


class DummyRoutineWithQueue(Routine):
    def __init__(self, queue, *args, **kwargs):
        super().__init__(logger=logging.getLogger("test_logs.log"), *args, **kwargs)
        self.queue = queue

    def main_logic(self, *args, **kwargs):
        self.metrics_collector.collect_latency(0.1, self.component_name)
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass

    @staticmethod
    def get_constructor_parameters():
        dicts = Routine.get_constructor_parameters()
        dicts.update({
            "queue": "QueueOut"
        })
        return dicts

    def does_routine_use_queue(self, queue):
        return self.queue == queue
