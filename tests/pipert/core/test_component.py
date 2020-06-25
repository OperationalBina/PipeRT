import time
from threading import Thread
from multiprocessing import Process
from tests.pipert.core.utils.dummy_routine import DummyRoutine
from tests.pipert.core.utils.dummy_component import DummyComponent


def test_register_routine():
    comp = DummyComponent()
    rout = DummyRoutine().as_thread()
    comp.register_routine(rout)

    assert rout in comp._routines.values()
    assert rout.stop_event == comp.stop_event


def test_safe_stop():

    def foo():
        print("bar")

    comp = DummyComponent()
    rout1 = DummyRoutine().as_thread()
    comp.register_routine(rout1)
    rout2 = Thread(target=foo)
    comp.register_routine(rout2)
    rout3 = Process(target=foo)
    comp.register_routine(rout3)

    comp.run()
    time.sleep(0.1)
    assert comp.stop_run() == 0


def test_change_runner():
    comp = DummyComponent()
    comp.as_thread()
    thread_runner = comp.runner_creator
    comp.as_process()
    process_runner = comp.runner_creator
    assert thread_runner != process_runner
