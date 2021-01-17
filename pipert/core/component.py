import threading
import os
if os.environ.get('TORCHVISION', 'no') == 'yes':
    from torch.multiprocessing import Event, Process
else:
    from multiprocessing import Event, Process
from pipert.core.routine import Routine
from threading import Thread
from typing import Union
import signal
import gevent
from pipert.core.metrics_collector import NullCollector
import sys
if sys.version_info.minor == 8:
    from pipert.core.multiprocessing_shared_memory import MpSharedMemoryGenerator as smGen
else:
    from pipert.core.shared_memory import SharedMemoryGenerator as smGen
from pipert.core.errors import RegisteredException, QueueDoesNotExist
from pipert.core.class_factory import ClassFactory
from queue import Queue
import logging
from logging.handlers import TimedRotatingFileHandler


class BaseComponent:

    def __init__(self, component_config, start_component=False):
        self.name = ""
        self.ROUTINES_FOLDER_PATH = "pipert/contrib/routines"
        self.MONITORING_SYSTEMS_FOLDER_PATH = "pipert/contrib/metrics_collectors"
        self.use_memory = False
        self.stop_event = Event()
        self.stop_event.set()
        self.queues = {}
        self._routines = {}
        self.metrics_collector = NullCollector()
        self.logger = logging.getLogger(self.name)
        self.setup_component(component_config)
        self.metrics_collector.setup()
        if start_component:
            self.run_comp()

    def _setup_logger(self):
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        log_file = os.environ.get("LOGS_FOLDER_PATH",
                                  "pipert/utils/log_files") + "/" + self.name + ".log"
        file_handler = TimedRotatingFileHandler(log_file, when='midnight')
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        self.logger.addHandler(file_handler)

    def setup_component(self, component_config):
        if (component_config is None) or (type(component_config) is not dict) or\
                (component_config == {}):
            return
        component_name, component_parameters = list(component_config.items())[0]
        self.name = component_name

        self._setup_logger()

        if ("shared_memory" in component_parameters) and \
                (component_parameters["shared_memory"]):
            self.use_memory = True
            self.generator = smGen(self.name)

        if "monitoring_system" in component_parameters:
            self.set_monitoring_system(component_parameters["monitoring_system"])

        for queue in component_parameters["queues"]:
            self.create_queue(queue_name=queue, queue_size=1)

        routine_factory = ClassFactory(self.ROUTINES_FOLDER_PATH)
        for routine_name, routine_parameters_real in component_parameters["routines"].items():
            routine_parameters = routine_parameters_real.copy()
            routine_parameters["name"] = routine_name
            routine_parameters['metrics_collector'] = self.metrics_collector
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
        self.logger.info("Running all routines")
        for routine in self._routines.values():
            routine.start()
            self.logger.info("{0} Started".format(routine.name))

    def run_comp(self):
        """
        Starts running all the component's routines.
        """
        self.logger.info("Running component")
        self.stop_event.clear()
        self._start()
        gevent.signal_handler(signal.SIGTERM, self.stop_run)

    def register_routine(self, routine: Union[Routine, Process, Thread]):
        """
        Registers routine to the list of component's routines
        Args:
            routine: the routine to register
        """
        self.logger.info("Registering routine")
        self.logger.info(routine)
        # TODO - write this function in a cleaner way?
        if isinstance(routine, Routine):
            if routine.name in self._routines:
                self.logger.error("Routine name already exist")
                raise RegisteredException("routine name already exist")
            if routine.stop_event is None:
                routine.stop_event = self.stop_event
                if self.use_memory:
                    routine.use_memory = self.use_memory
                    routine.generator = self.generator
            else:
                self.logger.error("Routine is already registered")
                raise RegisteredException("routine is already registered")
            self.logger.info("Routine registered")
            self._routines[routine.name] = routine
        else:
            self.logger.info("Routine registered")
            self._routines[routine.__str__()] = routine

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
        self.logger.info("Stopping component")
        if self.stop_event.is_set():
            return 0
        self.stop_event.set()

        try:
            self._teardown_callback()
            if self.use_memory:
                self.logger.info("Cleaning shared memory")
                self.generator.cleanup()
            for routine in self._routines.values():
                self.logger.info("Stopping routine {0}".format(routine.name))
                if isinstance(routine, Routine):
                    routine.runner.join()
                elif isinstance(routine, (Process, Thread)):
                    routine.join()
                self.logger.info("Routine {0} stopped".format(routine.name))
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
        if queue_name not in self.queues:
            raise QueueDoesNotExist(queue_name)
        if self.does_routines_use_queue(queue_name=queue_name):
            return False
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

    def is_component_running(self):
        return not self.stop_event.is_set()

    def get_routines(self):
        return self._routines

    def get_component_configuration(self):
        component_dict = {
            "shared_memory": self.use_memory,
            "queues":
                list(self.get_all_queue_names()),
            "routines": {}
        }

        if type(self).__name__ != BaseComponent.__name__:
            component_dict["component_type_name"] = type(self).__name__
        for current_routine_object in self._routines.values():
            routine_creation_dict = \
                self._get_routine_creation(current_routine_object)
            routine_name = routine_creation_dict.pop("name")
            component_dict["routines"][routine_name] = \
                routine_creation_dict
        return {self.name: component_dict}

    def _get_routine_creation(self, routine):
        routine_dict = routine.get_creation_dictionary()
        routine_dict["routine_type_name"] = routine.__class__.__name__
        for routine_param_name in routine_dict.keys():
            if "queue" in routine_param_name:
                for queue_name in self.queues.keys():
                    if getattr(routine, routine_param_name) is \
                            self.queues[queue_name]:
                        routine_dict[routine_param_name] = queue_name

        return routine_dict

    def set_monitoring_system(self, monitoring_system_parameters):
        monitoring_system_factory = ClassFactory(self.MONITORING_SYSTEMS_FOLDER_PATH)
        if "name" not in monitoring_system_parameters:
            print("No name parameter found inside the monitoring system")
            return
        monitoring_system_name = monitoring_system_parameters.pop("name") + "Collector"
        monitoring_system_class = monitoring_system_factory.get_class(monitoring_system_name)
        if monitoring_system_class is None:
            return
        try:
            self.metrics_collector = monitoring_system_class(**monitoring_system_parameters)
        except TypeError:
            print("Bad parameters given for the monitoring system " + monitoring_system_name)

    def set_routine_attribute(self, routine_name, attribute_name, attribute_value):
        routine = self._routines.get(routine_name, None)
        if routine is not None:
            setattr(routine, attribute_name, attribute_value)
