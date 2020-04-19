from splunk_http_event_collector import http_event_collector

from pipert.core.metrics_collector import MetricsCollector


class SplunkCollector(MetricsCollector):
    http_event_collector_key = "KEY"
    http_event_collector_host = "HOST"

    def __init__(self):
        super().__init__()
        self.HEC_sender = http_event_collector(self.http_event_collector_key,
                                               self.http_event_collector_host)

    def setup(self):
        pass

    def collect_execution_time(self, execution_time, routine_name, component_name):
        event = {"fields": {"metric_name:execution_time": execution_time,
                            "routine": routine_name,
                            "component": component_name}}
        self.HEC_sender.batchEvent(event)

    def collect_latency(self, latency, output_component):
        event = {"fields": {"metric_name:latency": latency,
                            "output_component": output_component}}
        self.HEC_sender.batchEvent(event)
