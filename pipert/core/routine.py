import time
import traceback
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
import logging
import threading
from logging.handlers import TimedRotatingFileHandler
import os
if os.environ.get('TORCHVISION', 'no') == 'yes':
    import torch.multiprocessing as mp
else:
    import multiprocessing as mp
from .errors import NoRunnerException
from .metrics_collector import NullCollector


class Events(Enum):
    """
    Events that are fired by the :class:`~core.RoutineInterface` during
    execution."""
    BEFORE_LOGIC = "before_logic"
    AFTER_LOGIC = "after_logic"
    EXCEPTION_RAISED = "exception_raised"


class State(object):
    """
    An object that is used to pass internal and user-defined state between
    event handlers."""

    def __init__(self):
        self.count = 0
        self.success = 0
        self.output = None


class RoutineTypes(Enum):
    """
    Every routine will have a type
    """
    NO_TYPE = -1
    INPUT = 0
    PROCESSING = 1
    OUTPUT = 2


class Routine(ABC):
    routine_type = RoutineTypes.NO_TYPE

    def __init__(self, name="", component_name="", extensions=None, metrics_collector=NullCollector(), *args, **kwargs):

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
        self.register_events(*Events)
        self.runner = None
        self.runner_creator = None
        self.runner_creator_kwargs = {}
        self._setup_logger()
        self._setup_extensions(extensions=extensions)

    def _setup_extensions(self, extensions):
        if extensions is None:
            return

        for extension_name, extension_params in extensions.items():
            try:
                getattr(self, "_extension_" + extension_name)(**extension_params)
            except AttributeError:
                self.logger.error("No extension with name '%s' was found", extension_name)

    def _setup_logger(self):
        self.logger = logging.getLogger(self.component_name + "." + self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        log_file = os.environ.get("LOGS_FOLDER_PATH", "pipert/utils/log_files") + "/" +\
            self.component_name + "-" + self.name + ".log"
        file_handler = TimedRotatingFileHandler(log_file, when='midnight')
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        self.logger.addHandler(file_handler)

    def register_events(self, *event_names):
        """
        Add events that can be fired.

        Registering an event will let the user fire these events at any point.
        This opens the door to make the :meth:`~ignite.routine.Routine.run` loop
        even more configurable.

        By default, the events from :class:`~ignite.routine.Events` are
        registerd.

        Args:
            *event_names: An object (ideally a string or int) to define the
                name of the event being supported.

        Example usage:

        .. code-block:: python

            from enum import Enum

            class Custom_Events(Enum):
                FOO_EVENT = "foo_event"
                BAR_EVENT = "bar_event"

            routine = Routine(process_function)
            routine.register_events(*Custom_Events)

        """
        for name in event_names:
            self._allowed_events.append(name)

    def add_event_handler(self, event_name, handler, first=False,
                          last=False, *args, **kwargs):
        """
        Add an event handler to be executed when the specified event is
        fired.

        Args:
            event_name: An event to attach the handler to. Valid events are
            from :class:`~ignite.routine.Events` or any `event_name` added by
             :meth:`~ignite.routine.Routine.register_events`.
            handler (callable): the callable event handler that
            should be invoked
            first: specify 'true' if the event handler should be called first
            last: specify 'true' if the event handler should be called last
            *args: additional args to be passed to `handler`.
            **kwargs: additional keyword args to be passed to `handler`.

        Notes:
              The handler function's first argument will be `self`, the
              :class:`~ignite.routine.Routine` object it was bound to.

              Note that other arguments can be passed to the handler in
              addition to the `*args` and  `**kwargs` passed here, for example
               during :attr:`~ignite.routine.Events.EXCEPTION_RAISED`.

        Example usage:

        .. code-block:: python

            routine = Routine(process_function)

            def print_epoch(routine):
                print("Epoch: {}".format(routine.state.epoch))

            routine.add_event_handler(Events.EPOCH_COMPLETED, print_epoch)

        """
        if event_name not in self._allowed_events:
            self.logger.error("attempt to add event handler to an invalid "
                              "event %s.", event_name)
            raise ValueError("Event {} is not a valid event for this "
                             "Routine.".format(event_name))

        if first:
            self._event_handlers[event_name].append((0,
                                                     (handler, args, kwargs)))
        elif last:
            self._event_handlers[event_name].append((2,
                                                     (handler, args, kwargs)))
        else:
            self._event_handlers[event_name].append((1,
                                                     (handler, args, kwargs)))

        # Sort the event handler list in an ascending order by the priority
        # in order to guarantee an execution order of the handlers.
        self._event_handlers[event_name] = \
            sorted(self._event_handlers[event_name], key=lambda x: x[0])
        self.logger.debug("added handler for event %s.", event_name)

    def has_event_handler(self, handler, event_name=None):
        """
        Check if the specified event has the specified handler.

        Args:
            handler (callable): the callable event handler.
            event_name: The event the handler attached to. Set this
                to ``None`` to search all events.
        """
        if event_name is not None:
            if event_name not in self._event_handlers:
                return False
            events = [event_name]
        else:
            events = self._event_handlers
        for e in events:
            for priority, (h, _, _) in self._event_handlers[e]:
                if h == handler:
                    return True
        return False

    def remove_event_handler(self, handler, event_name):
        """
        Remove event handler `handler` from registered handlers of the
        routine

        Args:
            handler (callable): the callable event handler that should
            be removed
            event_name: The event the handler attached to.

        """
        if event_name not in self._event_handlers:
            raise ValueError(f"Input event name '{event_name}' does not exist")

        current_event_handlers = self._event_handlers[event_name]
        new_event_handlers = [(priority, h) for priority, h in
                              current_event_handlers if h[0] != handler]
        if len(new_event_handlers) == len(current_event_handlers):
            raise ValueError("Input handler '{}' is not found among registered"
                             " event handlers".format(handler))
        self._event_handlers[event_name] = new_event_handlers

    def _extension_pace(self, fps):
        """
        Pace the routine to work at a wanted fps

        Args:
            fps: The wanted fps for the routine
        """
        def start_time(routine: Routine):
            routine.state.start_time = time.time()

        def start_pacing(routine: Routine, required_fps=0):
            elapsed_time = (time.time() - routine.state.start_time)
            excess_time = (1 / required_fps) - elapsed_time
            if excess_time > 0:
                time.sleep(excess_time)

        self.add_event_handler(Events.BEFORE_LOGIC, start_time, first=True, logger=self.logger)
        self.add_event_handler(Events.AFTER_LOGIC,
                               start_pacing,
                               last=True,
                               logger=self.logger,
                               required_fps=fps)
        print("singed pacer")

    def on(self, event_name, *args, **kwargs):
        """
        Decorator shortcut for add_event_handler.

        Args:
            event_name: An event to attach the handler to. Valid events are
            from :class:`~ignite.routine.Events` or any `event_name` added by
             :meth:`~ignite.routine.Routine.register_events`.
            *args: additional args to be passed to `handler`.
            **kwargs: additional keyword args to be passed to `handler`.

        """
        def decorator(f):
            self.add_event_handler(event_name, f, *args, **kwargs)
            return f
        return decorator

    def _fire_event(self, event_name, *event_args, **event_kwargs):
        """
        Execute all the handlers associated with given event.

        This method executes all handlers associated with the event
        `event_name`. Optional positional and keyword arguments can be used to
        pass arguments to **all** handlers added with this event. These
        aguments updates arguments passed using
        :meth:`~ignite.routine.Routine.add_event_handler`.

        Args:
            event_name: event for which the handlers should be executed. Valid
                events are from :class:`~ignite.routine.Events` or any
                `event_name` added by
                 :meth:`~ignite.routine.Routine.register_events`.
            *event_args: additional args to be passed to all handlers.
            **event_kwargs: additional keyword args to be passed to
            all handlers.

        """
        if event_name in self._allowed_events:
            # self.logger.debug("firing handlers for event %s ", event_name)
            for p, (func, args, kwargs) in self._event_handlers[event_name]:
                kwargs.update(event_kwargs)
                func(self, *(event_args + args), **kwargs)

    @abstractmethod
    def main_logic(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def setup(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, *args, **kwargs):
        raise NotImplementedError

    # TODO - replace plain 'setup()' and 'cleanup()' with context manager
    def _extended_run(self):
        """

        Returns:

        """
        self.state = State()
        # TODO - how to pass different args to setup/cleanup/main_logic?
        self.setup()
        # TODO - maybe add _fire_event before and after the while loop?
        while not self.stop_event.is_set():
            self._fire_event(Events.BEFORE_LOGIC)
            tick = time.time()
            try:
                self.state.output = self.main_logic()
            except Exception as error:
                self.logger.error("The routine has crashed: " + str(error))
                self.logger.error(str(traceback.format_exc()))
                self.state.output = False
            self.state.count += 1
            tock = time.time()

            if self.state.output:
                self.metrics_collector.collect_execution_time(tock - tick, self.name, self.component_name)
                self.state.success += 1
            self._fire_event(Events.AFTER_LOGIC)

        self.cleanup()

    def as_thread(self):
        self.runner_creator = threading.Thread
        self.runner_creator_kwargs = {"target": self._extended_run}
        return self

    def as_process(self):
        self.runner_creator = mp.Process
        self.runner_creator_kwargs = {"target": self._extended_run}
        return self

    def start(self):
        if self.runner_creator is None:
            # TODO - create better errors
            raise NoRunnerException("Runner not configured for routine")
        self.runner = self.runner_creator(**self.runner_creator_kwargs)
        self.runner.start()

    @staticmethod
    @abstractmethod
    def get_constructor_parameters():
        """
           Returns a dictionary of the constructor's
           parameters built as key for name and value
           for type name
        """
        return {
            "name": "String"
        }

    @abstractmethod
    def does_routine_use_queue(self, queue_name):
        """
           Returns True whether the routine uses the given
           queue_name.
           Args:
               queue_name: the name of the queue
        """
        raise NotImplementedError

    def get_creation_dictionary(self):
        """
           Returns a dictionary containing the routine parameters name as keys
           and their values as values. The method return queue objects instead
           of queue names when encountering them.
        """
        parameters_dictionary_with_routine_params = self.get_constructor_parameters()
        parameters_dictionary_with_all_params = self.__dict__
        for key in parameters_dictionary_with_routine_params.keys():
            parameters_dictionary_with_routine_params[key] = parameters_dictionary_with_all_params[key]
        return parameters_dictionary_with_routine_params
