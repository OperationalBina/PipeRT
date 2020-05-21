from pipert.core.routine import Routine


class DummyRoutineWithQueue(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        return self.queue == queue

    def __init__(self, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue

    def main_logic(self, *args, **kwargs):
        self.metrics_collector.collect_latency(0.1, self.component_name)
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass

