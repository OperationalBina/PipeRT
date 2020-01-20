import pytest
from torch.multiprocessing import Event
from pipert.core.routine import Routine, Events, State
from pipert.core.errors import NoRunnerException


class DummyRoutine(Routine):
    def __init__(self, name=""):
        super().__init__(name)

    def main_logic(self, *args, **kwargs):
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

