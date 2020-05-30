from torch.multiprocessing import Event, Process
from pipert.core.routine import Routine
from threading import Thread
from typing import Union
import signal
import gevent
from pipert.core.metrics_collector import NullCollector
from pipert.core.multiprocessing_shared_memory import MpSharedMemoryGenerator
from pipert.core.errors import RegisteredException, QueueDoesNotExist
from pipert.core.class_factory import ClassFactory
from queue import Queue


class BaseComponent:

    def __init__(self, component_config):
        self.name = ""
        self.ROUTINES_FOLDER_PATH = "pipert/contrib/routines"
        self.use_memory = False
        self.stop_event = Event()
        self.stop_event.set()
        self.queues = {}
        self._routines = {}
        self.component_runner = None
        self.runner_creator = None
        self.runner_creator_kwargs = {}
        self.as_process()
        self.metrics_collector = NullCollector()
        self.setup_component(component_config)
        self.run_comp()

    def setup_component(self, component_config):
        if (component_config is None) or (type(component_config) is not dict) or\
                (component_config == {}):
            return
        component_name, component_parameters = list(component_config.items())[0]
        self.name = component_name

        if component_parameters["shared_memory"]:
            self.use_memory = True
            self.generator = MpSharedMemoryGenerator(self.name)

        for queue in component_parameters["queues"]:
            self.create_queue(queue_name=queue, queue_size=1)

        routine_factory = ClassFactory(self.ROUTINES_FOLDER_PATH)
        for routine_name, routine_parameters in component_parameters["routines"].items():
            routine_parameters["name"] = routine_name
            routine_class = routine_factory.get_class(routine_parameters.pop("routine_type_name", ""))
            if routine_class is None:
                continue
            try:
                self._replace_queue_names_with_queue_objects(routine_parameters)
            except QueueDoesNotExist as e:
                continue

            routine_parameters["component_name"] = self.name

            self.register_routine(routine_class(**routine_parameters).as_thread())

    def _replace_queue_names_with_queue_objects(self, routine_parameters_kwargs):
        for key, value in routine_parameters_kwargs.items():
            if 'queue' in key.lower():
                routine_parameters_kwargs[key] = self.get_queue(queue_name=value)

    def _start(self):
        """
        Goes over the component's routines registered in self.routines and
        starts running them.
        """
        for routine in self._routines.values():
            routine.start()

    def run_comp(self):
        self.component_runner = self.runner_creator(**self.runner_creator_kwargs)
        self.component_runner.start()

    def _run(self):
        """
        Starts running all the component's routines.
        """
        self.stop_event.clear()
        self._start()
        gevent.signal_handler(signal.SIGTERM, self.stop_run)
        self.metrics_collector.setup()

        # keeps the component execution alive
        while not self.stop_event.is_set():
            pass
        self._stop_run()

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
                if self.use_memory:
                    routine.use_memory = self.use_memory
                    routine.generator = self.generator
            else:
                raise RegisteredException("routine is already registered")
            self._routines[routine.name] = routine
        else:
            self._routines[routine.__str__()] = routine

    def _teardown_callback(self, *args, **kwargs):
        """
        Implemented by subclasses of BaseComponent. Used for stopping or
        tearing down things that are not stopped by setting the stop_event.
        Returns: None
        """
        pass

    def stop_run(self):
        self.stop_event.set()
        try:
            self.component_runner.join()
            return 0
        except RuntimeError:
            print(f"Wasn't able to stop the component {self.name}")
            return 1

    def _stop_run(self):
        """
        Signals all the component's routines to stop.
        """
        try:
            self._teardown_callback()
            if self.use_memory:
                self.generator.cleanup()
            for routine in self._routines.values():
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
        return routine_name in self._routines

    def remove_routine(self, routine_name):
        if self.does_routine_name_exist(routine_name):
            del self._routines[routine_name]
            return True
        else:
            return False

    def does_routines_use_queue(self, queue_name):
        for routine in self._routines.values():
            if routine.does_routine_use_queue(self.queues[queue_name]):
                return True
        return False

    def as_thread(self):
        self.runner_creator = Thread
        self.runner_creator_kwargs = {"target": self._run}
        return self

    def as_process(self):
        self.runner_creator = Process
        self.runner_creator_kwargs = {"target": self._run}
        return self

    def does_component_running(self):
        return not self.stop_event.is_set()

    def get_routines(self):
        return self._routines