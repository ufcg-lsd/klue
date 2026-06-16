"""
ServiceMonitorWatcher watches Kubernetes node events and automatically
creates or deletes the corresponding Prometheus ServiceMonitor for each
KWOK fake node.
"""

import threading
from kubernetes import watch
from util.k8s_api.k8s_api import K8SAPI
from util.k8s_object_applier import KubernetesObjectApplier
from util.k8s_objects.servicemonitor_generator import ServiceMonitorGenerator


class ServiceMonitorManager:
    """
    Background thread that reacts to node ADDED/DELETED events and keeps
    ServiceMonitors in sync with the live set of KWOK fake nodes.
    """

    def __init__(self):
        self.k8s_api = K8SAPI()
        self.k8s_object_applier = KubernetesObjectApplier(self.k8s_api)
        self.servicemonitor_generator = ServiceMonitorGenerator()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="ServiceMonitorWatcher",
            daemon=True,
        )

    def log(self, message):
        print(f"[SERVICE MONITOR WATCHER] {message}", flush=True)

    def start(self):
        self.log("Starting.")
        self._thread.start()

    def stop(self):
        self.log("Stopping.")
        self._stop_event.set()
        self._thread.join()
        self.log("Stopped.")

    # ------------------------------------------------------------------
    # Watch loop
    # ------------------------------------------------------------------

    def _watch_loop(self):
        """
        Opens a Kubernetes watch on nodes. For each ADDED or DELETED event
        on a KWOK fake node, creates or deletes the ServiceMonitor.
        Reconnects automatically if the watch stream closes, resuming from
        the last seen resourceVersion to avoid replaying existing nodes.
        """
        # List existing nodes once on startup to get the current resourceVersion.
        node_list = self.k8s_api.v1.list_node()
        resource_version = node_list.metadata.resource_version
        for node in node_list.items:
            if self._is_fake_node(node):
                self._on_node_added(node.metadata.name)

        w = watch.Watch()
        while not self._stop_event.is_set():
            try:
                for event in w.stream(
                    self.k8s_api.v1.list_node,
                    timeout_seconds=60,
                    resource_version=resource_version,
                ):
                    if self._stop_event.is_set():
                        break

                    node = event["object"]
                    event_type = event["type"]
                    resource_version = node.metadata.resource_version

                    if not self._is_fake_node(node):
                        continue

                    node_name = node.metadata.name

                    if event_type == "ADDED":
                        self._on_node_added(node_name)
                    elif event_type == "DELETED":
                        self._on_node_deleted(node_name)

            except Exception as e:
                if not self._stop_event.is_set():
                    self.log(f"[WARNING] Watch error, reconnecting: {e}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_node_added(self, node_name: str):
        try:
            self.k8s_api.v1.patch_node(node_name, {
                "metadata": {
                    "annotations": {
                        "metrics.k8s.io/resource-metrics-path": f"/metrics/nodes/{node_name}/metrics/resource"
                    }
                }
            })
            self.log(f"[INFO] Patched metrics annotation for node {node_name}.")
        except Exception as e:
            self.log(f"[WARNING] Failed to patch annotation for node {node_name}: {e}")

        try:
            service_monitor = self.servicemonitor_generator.generate_service_monitor(node_name)
            self.k8s_object_applier.apply_service_monitor(service_monitor, node_name)
            self.log(f"[INFO] ServiceMonitor created for node {node_name}.")
        except Exception as e:
            self.log(f"[ERROR] Failed to create ServiceMonitor for node {node_name}: {e}")

    def _on_node_deleted(self, node_name: str):
        try:
            self.k8s_api.delete_namespaced_custom_object(
                "monitoring.coreos.com", "v1", "monitoring", "servicemonitors", node_name
            )
            self.log(f"[INFO] ServiceMonitor deleted for node {node_name}.")
        except Exception as e:
            self.log(f"[WARNING] Failed to delete ServiceMonitor for node {node_name}: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_fake_node(self, node) -> bool:
        return node.metadata.annotations and \
               node.metadata.annotations.get("kwok.x-k8s.io/node") == "fake"
