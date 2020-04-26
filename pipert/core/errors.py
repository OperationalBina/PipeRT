class NoRunnerException(Exception):
    """
    Exception class to raise if Routine doesn't have a configured runner
    """


class NoStopEventException(Exception):
    """
    Exception class to raise if Routine doesn't have a configured stop event
    """


class RegisteredException(Exception):
    """
    Exception class to raise if Routine is already registered to a component
    """


class QueueDoesNotExist(Exception):
    """
        Exception class to raise if Queue doesn't exist in a component
    """

    def __init__(self, queue_name):
        self.queue_name = queue_name

    def message(self):
        return "The queue " + self.queue_name + " doesn't exist"
