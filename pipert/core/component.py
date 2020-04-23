from torch.multiprocessing import Event, Process
from pipert.core.routine import Routine
from threading import Thread
from typing import Union
import signal
import gevent
from .metrics_collector import NullCollector
from .errors import RegisteredException, QueueDoesNotExist
from queue import Queue


class BaseComponent:

    def __init__(self, name="", metrics_collector=NullCollector(),
                 *args, **kwargs):
        """
        Args:
            *args: TBD
            **kwargs: TBD
        """
        super().__init__()
        self.name = name
        self.metrics_collector = metrics_collector
        self.stop_event = Event()
        self.stop_event.set()
        self.queues = {}
        self._routines = []

    def _start(self):
        """
        Goes over the component's routines registered in self.routines and
        starts running them.
        """
        for routine in self._routines:
            routine.start()

    def run(self):
        self._run()

    def _run(self):
        """
        Starts running all the component's routines.
        """
        self.stop_event.clear()
        self._start()
        gevent.signal(signal.SIGTERM, self.stop_run)
        self.metrics_collector.setup()

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
        Signals all the component's routines to stop.
        """
        try:
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

    def create_queue(self, queue_name, queue_size=1):
        """
           Create a new queue for the component.
           Returns True if created or False otherwise
           Args:
               queue_name: the name of the queue, must be unique
               queue_size: the size of the queue
        """
        if queue_name in self.queues:
            return False
        self.queues[queue_name] = Queue(maxsize=queue_size)
        return True

    def get_queue(self, queue_name):
        """
           Returns the queue object by its name
           Args:
               queue_name: the name of the queue
           Raises:
               KeyError - if no queue has the name
        """
        try:
            return self.queues[queue_name]
        except KeyError:
            raise QueueDoesNotExist(queue_name)

    def get_all_queue_names(self):
        """
           Returns the list of names of queues that
           the component expose.
        """
        return list(self.queues.keys())

    def does_queue_exist(self, queue_name):
        """
           Returns True the component has a queue named
           queue_name or False otherwise
           Args:
               queue_name: the name of the queue to check
        """
        return queue_name in self.queues

    def delete_queue(self, queue_name):
        """
           Deletes a queue with the name queue_name.
           Returns True if succeeded.
           Args:
               queue_name: the name of the queue to delete
           Raises:
               KeyError - if no queue has the name queue_name
        """
        try:
            del self.queues[queue_name]
            return True
        except KeyError:
            raise QueueDoesNotExist(queue_name)

    def does_routine_name_exist(self, routine_name):
        for routine in self._routines:
            if routine.name == routine_name:
                return True
        return False

    def remove_routine(self, routine_name):
        self._routines = [routine for routine in self._routines
                          if isinstance(routine, Routine)
                          and routine.name != routine_name]

    def does_routines_use_queue(self, queue_name):
        for routine in self._routines:
            if routine.does_routine_use_queue(self.queues[queue_name]):
                return True
        return False
