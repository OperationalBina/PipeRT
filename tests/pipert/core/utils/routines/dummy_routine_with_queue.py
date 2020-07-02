from collections import defaultdict
import multiprocessing as mp
from pipert.core.metrics_collector import NullCollector
from pipert.core.routine import Routine


class DummyRoutineWithQueue(Routine):
    def __init__(self, queue, name="", component_name="", metrics_collector=NullCollector(), *args, **kwargs):
        self.name = name
        # name of the component that instantiated the routine
        self.component_name = component_name
        self.metrics_collector = metrics_collector
        self.use_memory = False
        self.generator = None
        self.stop_event: mp.Event = None
        self._event_handlers = defaultdict(list)
        self.state = None
        self._allowed_events = []
        self.runner = None
        self.runner_creator = None
        self.runner_creator_kwargs = {}
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
