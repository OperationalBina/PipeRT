import logging

import pytest
import time
import os

if os.environ.get('TORCHVISION', 'no') == 'yes':
    from torch.multiprocessing import Event
else:
    from multiprocessing import Event
from pipert.core.routine import Routine, Events
from pipert.core.errors import NoRunnerException
from tests.pipert.core.utils.routines.dummy_routine import DummyRoutine, dummy_before_stop_handler


class DummySleepRoutine(Routine):
    @staticmethod
    def get_constructor_parameters():
        pass

    def does_routine_use_queue(self, queue):
        pass

    def __init__(self, sleep_time, name=""):
        super().__init__(name)
        self.stop_event = Event()
        self.sleep_time = sleep_time

    def _setup_logger(self):
        self.logger = logging.getLogger("test_logs.log")

    def main_logic(self, *args, **kwargs):
        time.sleep(self.sleep_time)
        return True

    def setup(self, *args, **kwargs):
        pass

    def cleanup(self, *args, **kwargs):
        pass


def dummy_before_handler(routine):
    with pytest.raises(AttributeError):
        _ = routine.state.dummy
    routine.state.dummy = 666
    routine.stop_event.set()


def dummy_after_handler(routine):
    assert routine.state.dummy == 666
    routine.state.dummy += 1


def test_routine_as_thread():
    r = DummyRoutine()
    e = Event()
    r.stop_event = e
    r.as_thread()
    r.start()
    e.set()
    r.runner.join()


def test_routine_as_process():
    r = DummyRoutine()
    e = Event()
    r.stop_event = e
    r.as_process()
    r.start()
    e.set()
    r.runner.join()


def test_routine_no_runner():
    r = DummyRoutine(name="dummy")
    with pytest.raises(NoRunnerException):
        r.start()
    e = Event()
    r.stop_event = e
    r.as_thread()
    try:
        r.start()
    except NoRunnerException:
        pytest.fail("NoRunnerException was thrown...")
    e.set()
    r.runner.join()


def test_add_event_handler():
    r = DummyRoutine()
    e = Event()
    r.stop_event = e
    r.as_thread()
    r.add_event_handler(Events.BEFORE_LOGIC, dummy_before_handler)
    r.add_event_handler(Events.AFTER_LOGIC, dummy_after_handler)

    @r.on(Events.AFTER_LOGIC)
    def dummy_handler(_):
        pass

    r.start()
    r.runner.join()
    assert r.state.dummy == 667


def test_has_event_handler():
    r = DummyRoutine()

    assert not r.has_event_handler(dummy_before_handler, Events.BEFORE_LOGIC)
    assert not r.has_event_handler(dummy_before_handler)

    r.add_event_handler(Events.BEFORE_LOGIC, dummy_before_handler)
    assert r.has_event_handler(dummy_before_handler, Events.BEFORE_LOGIC)
    assert r.has_event_handler(dummy_before_handler)

    with pytest.raises(ValueError):
        r.add_event_handler("wrong_event", dummy_before_handler)


def test_remove_event_handler():
    r = DummyRoutine()
    with pytest.raises(ValueError):
        r.remove_event_handler(dummy_before_handler, Events.BEFORE_LOGIC)
    r.add_event_handler(Events.BEFORE_LOGIC, dummy_before_handler)
    assert r.has_event_handler(dummy_before_handler)
    r.remove_event_handler(dummy_before_handler, Events.BEFORE_LOGIC)
    assert not r.has_event_handler(dummy_before_handler)
    with pytest.raises(ValueError):
        r.remove_event_handler(dummy_before_handler, Events.BEFORE_LOGIC)


def test_pacer_faster_pace():
    fast_routine = DummySleepRoutine(1 / 60)
    fast_routine._extension_pace(2)
    fast_routine.add_event_handler(Events.AFTER_LOGIC,
                                   dummy_before_stop_handler,
                                   first=True)
    fast_routine.as_thread()
    start_time = time.time()
    fast_routine.start()
    fast_routine.runner.join()
    elapsed_time = time.time()
    assert round(elapsed_time - start_time, 1) == round(0.5, 1)  # 2 fps is 0.5 sec for frame


def test_pacer_slower_pace():
    slow_routine = DummySleepRoutine(1 / 1)
    slow_routine._extension_pace(2)
    slow_routine.add_event_handler(Events.AFTER_LOGIC,
                                   dummy_before_stop_handler,
                                   first=True)
    slow_routine.as_thread()
    start_time = time.time()
    slow_routine.start()
    slow_routine.runner.join()
    elapsed_time = time.time()
    assert round(elapsed_time - start_time, 1) == round(1 / 1, 1)


def test_setup_extensions():
    extension = {
        "dummy": {
        }
    }
    r = DummyRoutine(extensions=extension)
    assert r.has_event_handler(dummy_before_stop_handler)


def test_setup_not_existing_extension():
    extension = {
        "dummy123": {
            "bla": 2
        }
    }
    r = DummyRoutine(extensions=extension)
    assert len(r._event_handlers) == 0
