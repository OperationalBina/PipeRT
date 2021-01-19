import os
import time
from pipert.core.routine import Routine, Events
if os.environ.get('TORCHVISION', 'no') == 'yes':
    from torch.multiprocessing import Event
else:
    from multiprocessing import Event
import logging


class DummyCrashingRoutine(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        pass

    def __init__(self, name=""):
        super().__init__(logger=logging.getLogger("test_logs.log"), name=name)
        self.x = {}

    def main_logic(self, *args, **kwargs):
        a = self.x["bug"]
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass


class DummySleepRoutine(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        pass

    def __init__(self, sleep_time, name=""):
        super().__init__(logger=logging.getLogger("test_logs.log"), name=name)
        self.stop_event = Event()
        self.sleep_time = sleep_time

    def main_logic(self, *args, **kwargs):
        time.sleep(self.sleep_time)
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass


def dummy_before_stop_handler(routine):
    print("Stopping routine")
    routine.stop_event.set()


class DummyRoutine(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        return False

    def __init__(self, *args, **kwargs):
        super().__init__(logger=logging.getLogger("test_logs.log"), *args, **kwargs)

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

