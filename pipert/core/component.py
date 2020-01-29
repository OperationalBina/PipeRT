from torch.multiprocessing import Event, Process
from pipert.core.routine import Routine
from threading import Thread
from typing import Union
import signal
import gevent
import zerorpc
from .errors import RegisteredException


class BaseComponent:

    def __init__(self, endpoint="tcp://0.0.0.0:4242", name="", *args, **kwargs):
        """
        Args:
            endpoint: the endpoint the component's zerorpc server will listen
            in.
            *args: TBD
            **kwargs: TBD
        """
        super().__init__()
        self.name = name
        self.stop_event = Event()
        self.endpoint = endpoint
        self._routines = []
        self.zrpc = zerorpc.Server(self)
        self.zrpc.bind(endpoint)

    def _start(self):
        """
        Goes over the component's routines registered in self.routines and
        starts running them.
        """
        for routine in self._routines:
            routine.start()

    def run(self):
        """
        Starts running all the component's routines and the zerorpc server.
        """
        self._start()
        gevent.signal(signal.SIGTERM, self.stop_run)
        self.zrpc.run()
        self.zrpc.close()

    def register_routine(self, routine: Union[Routine, Process, Thread]):
        """
        Registers routine to the list of component's routines
        Args:
            routine: the routine to register
        """
        # TODO - write this function in a cleaner way?
        if isinstance(routine, Routine):
            if routine.stop_event is None:
                routine.stop_event = self.stop_event
            else:
                raise RegisteredException("routine is already registered")
        self._routines.append(routine)

    def _teardown_callback(self, *args, **kwargs):
        """
        Implemented by subclasses of BaseComponent. Used for stopping or
        tearing down things that are not stopped by setting the stop_event.
        Returns: None
        """
        pass

    def stop_run(self):
        """
        Signals all the component's routines to stop and then stops the zerorpc
        server.
        """
        try:
            self.zrpc.stop()
            self.stop_event.set()
            self._teardown_callback()
            for routine in self._routines:
                if isinstance(routine, Routine):
                    routine.runner.join()
                elif isinstance(routine, (Process, Thread)):
                    routine.join()
            return 0
        except RuntimeError:
            return 1
