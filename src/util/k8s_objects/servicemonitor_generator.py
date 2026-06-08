"""
ServiceMonitorGenerator is a utility class for generating Kubernetes ServiceMonitor
custom resource objects (monitoring.coreos.com/v1).

A ServiceMonitor is created for each KWOK node so that Prometheus and the
metrics-server can scrape per-node resource metrics exposed by the KWOK
controller at: /metrics/nodes/<node-name>/metrics/resource
"""

class ServiceMonitorGenerator:
    """
    A class responsible for generating ServiceMonitor custom resource objects
    for each KWOK node created in the cluster.
    """

    def __init__(self):
        """
        Initializes the ServiceMonitorGenerator.
        """
        self.SERVICE_MONITOR_API_GROUP   = "monitoring.coreos.com"
        self.SERVICE_MONITOR_API_VERSION = "v1"

        self.MONITORING_NAMESPACE        = "monitoring"
        self.KWOK_CONTROLLER_NAMESPACE   = "kube-system"
        self.KWOK_CONTROLLER_LABEL       = "kwok-controller"
        self.DEFAULT_SCRAPE_INTERVAL     = "15s"

    def generate_service_monitor(self, node_name: str) -> dict:
        """
        Generates a ServiceMonitor object definition for the given KWOK node.

        Args:
            node_name (str): The name of the KWOK node (e.g. "kwok-node-0").
                             Used to build the metrics scrape path and the
                             ServiceMonitor resource name.

        Returns:
            dict: A dictionary representing the ServiceMonitor object,
                  ready for YAML/JSON serialization.
        """

        metrics_path = f"/metrics/nodes/{node_name}/metrics/resource"

        metadata = {
            "name": node_name,
            "namespace": self.MONITORING_NAMESPACE,
        }

        endpoints = [
            {
                "port": "http",
                "path": metrics_path,
                "interval": self.DEFAULT_SCRAPE_INTERVAL,
            }
        ]

        spec = {
            "selector": {
                "matchLabels": {
                    "app": self.KWOK_CONTROLLER_LABEL,
                }
            },
            "namespaceSelector": {
                "matchNames": [self.KWOK_CONTROLLER_NAMESPACE],
            },
            "endpoints": endpoints,
        }

        service_monitor_definition = {
            "apiVersion": f"{self.SERVICE_MONITOR_API_GROUP}/{self.SERVICE_MONITOR_API_VERSION}",
            "kind": "ServiceMonitor",
            "metadata": metadata,
            "spec": spec,
        }

        return service_monitor_definition