from pipert.core.metrics_collector import MetricsCollector


class DummyCollector(MetricsCollector):

    def __init__(self, parameter):
        super().__init__()
        self.parameter = parameter

    def setup(self):
        pass

    def collect_execution_time(self, execution_time, routine_name, component_name):
        print("collected execute time", self.parameter)

    def collect_latency(self, latency, output_component):
        print("collected latency", self.parameter)
