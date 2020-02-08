from collections import defaultdict
from enum import Enum
import logging
import threading
from logging.handlers import TimedRotatingFileHandler

import torch.multiprocessing as mp
from .errors import NoRunnerException


class Events(Enum):
    """Events that are fired by the :class:`~core.RoutineInterface` during
    execution."""
    BEFORE_LOGIC = "before_logic"
    AFTER_LOGIC = "after_logic"
    EXCEPTION_RAISED = "exception_raised"


class State(object):
    """An object that is used to pass internal and user-defined state between
    event handlers."""

    def __init__(self):
        self.count = 0
        self.success = 0
        self.output = None


class Routine:

    def __init__(self, name="", component_name=""):

        self.name = name

        # name of the component that instantiated the routine
        self.component_name = component_name

        self.stop_event: mp.Event = None
        self._event_handlers = defaultdict(list)
        self.state = None
        self._allowed_events = []
        self.register_events(*Events)
        self.runner = None
        # setting up the routine's logger
        self.logger = logging.getLogger(self.component_name + "." +
                                        self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        log_file = "pipeline.log"
        file_handler = TimedRotatingFileHandler(log_file, when='midnight')
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s — %(name)s — %(levelname)s — %(message)s"))
        self.logger.addHandler(file_handler)

    def register_events(self, *event_names):
        """Add events that can be fired.

        Registering an event will let the user fire these events at any point.
        This opens the door to make the :meth:`~ignite.engine.Engine.run` loop
        even more configurable.

        By default, the events from :class:`~ignite.engine.Events` are
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

            engine = Engine(process_function)
            engine.register_events(*Custom_Events)

        """
        for name in event_names:
            self._allowed_events.append(name)

    def add_event_handler(self, event_name, handler, *args, **kwargs):
        """Add an event handler to be executed when the specified event is
        fired.

        Args:
            event_name: An event to attach the handler to. Valid events are
            from :class:`~ignite.engine.Events` or any `event_name` added by
             :meth:`~ignite.engine.Engine.register_events`.
            handler (callable): the callable event handler that
            should be invoked
            *args: argsional args to be passed to `handler`.
            **kwargs: argsional keyword args to be passed to `handler`.

        Notes:
              The handler function's first argument will be `self`, the
              :class:`~ignite.engine.Engine` object it was bound to.

              Note that other arguments can be passed to the handler in
              addition to the `*args` and  `**kwargs` passed here, for example
               during :attr:`~ignite.engine.Events.EXCEPTION_RAISED`.

        Example usage:

        .. code-block:: python

            engine = Engine(process_function)

            def print_epoch(engine):
                print("Epoch: {}".format(engine.state.epoch))

            engine.add_event_handler(Events.EPOCH_COMPLETED, print_epoch)

        """
        if event_name not in self._allowed_events:
            self.logger.error("attempt to add event handler to an invalid "
                              "event %s.", event_name)
            raise ValueError("Event {} is not a valid event for this "
                             "Engine.".format(event_name))

        self._event_handlers[event_name].append((handler, args, kwargs))
        self.logger.debug("added handler for event %s.", event_name)

    def has_event_handler(self, handler, event_name=None):
        """Check if the specified event has the specified handler.

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
            for h, _, _ in self._event_handlers[e]:
                if h == handler:
                    return True
        return False

    def remove_event_handler(self, handler, event_name):
        """Remove event handler `handler` from registered handlers of the
        engine

        Args:
            handler (callable): the callable event handler that should
            be removed
            event_name: The event the handler attached to.

        """
        if event_name not in self._event_handlers:
            raise ValueError(f"Input event name '{event_name}' does not exist")

        new_event_handlers = [(h, args, kwargs) for h, args, kwargs in
                              self._event_handlers[event_name] if h != handler]
        if len(new_event_handlers) == len(self._event_handlers[event_name]):
            raise ValueError("Input handler '{}' is not found among registered"
                             " event handlers".format(handler))
        self._event_handlers[event_name] = new_event_handlers

    def on(self, event_name, *args, **kwargs):
        """Decorator shortcut for add_event_handler.

        Args:
            event_name: An event to attach the handler to. Valid events are
            from :class:`~ignite.engine.Events` or any `event_name` added by
             :meth:`~ignite.engine.Engine.register_events`.
            *args: argsional args to be passed to `handler`.
            **kwargs: argsional keyword args to be passed to `handler`.

        """
        def decorator(f):
            self.add_event_handler(event_name, f, *args, **kwargs)
            return f
        return decorator

    def _fire_event(self, event_name, *event_args, **event_kwargs):
        """Execute all the handlers associated with given event.

        This method executes all handlers associated with the event
        `event_name`. Optional positional and keyword arguments can be used to
        pass arguments to **all** handlers added with this event. These
        aguments updates arguments passed using
        :meth:`~ignite.engine.Engine.add_event_handler`.

        Args:
            event_name: event for which the handlers should be executed. Valid
                events are from :class:`~ignite.engine.Events` or any
                `event_name` added by
                 :meth:`~ignite.engine.Engine.register_events`.
            *event_args: argsional args to be passed to all handlers.
            **event_kwargs: argsional keyword args to be passed to
            all handlers.

        """
        if event_name in self._allowed_events:
            # self.logger.debug("firing handlers for event %s ", event_name)
            for func, args, kwargs in self._event_handlers[event_name]:
                kwargs.update(event_kwargs)
                func(self, *(event_args + args), **kwargs)

    def main_logic(self, *args, **kwargs):
        raise NotImplementedError

    def setup(self, *args, **kwargs):
        raise NotImplementedError

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
            self.state.output = self.main_logic()
            self.state.count += 1
            if self.state.output:
                self.state.success += 1
            self._fire_event(Events.AFTER_LOGIC)

        self.cleanup()

    def as_thread(self):
        self.runner = threading.Thread(target=self._extended_run)
        return self

    def as_process(self):
        self.runner = mp.Process(target=self._extended_run)
        return self

    def start(self):
        if self.runner is None:
            # TODO - create better errors
            raise NoRunnerException("Runner not configured for routine")
        self.runner.start()
