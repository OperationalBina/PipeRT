from abc import ABC, abstractmethod


class MetricsCollector(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def collect_execution_time(self, execution_time, routine_name, component_name):
        """
        Saves the execution time of the routine's logic to the monitoring service that is being used.

        Args:
            execution_time: the time it took the routine to execute its main_logic function, in milliseconds.
            routine_name: the name of the relevant routine.
            component_name: the name of the routine's component.
        """
        pass

    @abstractmethod
    def collect_latency(self, latency, output_component):
        """
        Saves the end-to-end latency of the pipeline's longest path.
        The latency metric measures the time interval between the capture
        of a prediction's associated frame, and the output of that prediction's
        associated result (for example: a frame that contains the visualization of that prediction).

        Args:
            latency: the end-to-end latency, in milliseconds.
            output_component: the name of the pipeline's output component (for example: the flask display).
        """
        pass


class NullCollector(MetricsCollector):

    def __init__(self):
        super().__init__()

    def setup(self):
        pass

    def collect_execution_time(self, execution_time, routine_name, component_name):
        pass

    def collect_latency(self, latency, output_component):
        pass
