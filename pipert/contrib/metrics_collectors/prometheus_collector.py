from prometheus_client import Histogram, start_http_server
from prometheus_client.utils import INF

from pipert.core.metrics_collector import MetricsCollector


class PrometheusCollector(MetricsCollector):
    buckets = (0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05,
               0.1, 0.2, 0.5, 1, 2, 5, INF)

    REQUEST_TIME = Histogram('routine_processing_seconds',
                             'Time spent processing routine',
                             ['routine', 'component'],
                             buckets=buckets)

    REQUEST_LATENCY = Histogram('message_latency',
                                'End to end latency',
                                ['output_component'],
                                buckets=buckets)

    def __init__(self, port):
        super().__init__()
        self.port = port

    def setup(self):
        start_http_server(self.port)

    def collect_execution_time(self, execution_time, routine_name, component_name):
        self.REQUEST_TIME.labels(routine=routine_name,
                                 component=component_name) \
            .observe(execution_time)

    def collect_latency(self, latency, output_component):
        self.REQUEST_LATENCY.labels(output_component=output_component).observe(latency)