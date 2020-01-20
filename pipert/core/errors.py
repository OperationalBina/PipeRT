
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
