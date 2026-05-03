import multiprocessing
import queue

from kubernetes.client.rest import ApiException

from util.k8s_api.k8s_api import K8SAPI
from util.k8s_objects.cluster_resource_usage_generator import ClusterResourceUsageGenerator
from workload.usage_assignment import UsageAssignmentEngine


class UsageManager(multiprocessing.Process):
    """
    Background process responsible for managing KWOK ClusterResourceUsage objects.

    - Receives set-usage events with real pod-level usage snapshots.
    - Tracks workloads by (namespace, name).
    - Periodically checks the exact set of emulated pods for each tracked workload.
    - Reconciles when:
        1. a new set-usage event arrives; or
        2. the emulated pod set changes.
    - Delegates usage distribution to UsageAssignmentEngine.
    - Applies the returned assignment as one ClusterResourceUsage per emulated pod.
    """

    TIME_OUT = 200
    RECONCILE_INTERVAL_SECONDS = 5

    CRU_GROUP = "kwok.x-k8s.io"
    CRU_VERSION = "v1alpha1"
    CRU_PLURAL = "clusterresourceusages"

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

        # (namespace, workload_name) -> {
        #   (namespace, real_pod_name): {"cpu": float, "memory": float}
        # }
        self.last_usage_actions = {}

        # (namespace, workload_name) -> {(namespace, emulated_pod_name), ...}
        self.last_emulated_pods = {}

        # (namespace, workload_name) -> set(cru_name)
        self.managed_crus_by_workload = {}

        # set(cru_name)
        self.existing_crus = set()

    def log(self, message):
        print(f"[USAGE MANAGER] {message}", flush=True)

    def run(self):
        """
        Main execution loop.

        Waits for events from the queue. When no events arrive within
        the timeout window, a reconciliation loop runs to ensure CRU
        objects remain consistent with the current emulated pods set.
        """

        self.log("Process started")

        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.assignment_engine = UsageAssignmentEngine()
        self.cru_generator = ClusterResourceUsageGenerator()

        self.log("K8SAPI initialized")

        while True:
            try:
                event = self.queue.get(timeout=self.RECONCILE_INTERVAL_SECONDS)

                self.log(f"Event received: {event}")

                if event == "STOP":
                    self.log("Stopping UsageManager")
                    break

                self.handle_set_usage_event(event)

            except queue.Empty:
                # No event received -> perform periodic reconciliation
                self.reconcile_tracked_workloads()

    # --------------------------------------------------
    # Event handling
    # --------------------------------------------------

    def handle_set_usage_event(self, event):
        """
        Store the latest set-usage event for a workload and reconcile that workload.
        """

        namespace = event["namespace"]
        name = event["name"]
        workload_key = (namespace, name)

        usage_action = {}
        for pod_name, usage in event.get("pods").items():
            usage_action[(namespace, pod_name)] = {
                "cpu": usage.get("cpu", 0),
                "memory": usage.get("memory", 0)
            }

        self.last_usage_actions[workload_key] = usage_action

        self.reconcile_workload(
            workload_key=workload_key
        )

    # --------------------------------------------------
    # Reconciliation
    # --------------------------------------------------

    def reconcile_tracked_workloads(self):
        """
        Periodically check whether the exact emulated pod set changed.
        """

        for workload_key in list(self.last_usage_actions.keys()):
            namespace, name = workload_key

            try:
                emulated_pods = self.list_emulated_pods(namespace, name)
            except ApiException as e:
                if e.status == 404:
                    self.log(f"[INFO] Workload disappeared: {namespace}/{name}")
                    self.cleanup_workload(workload_key)
                    continue
                else:
                    self.log(f"[WARNING] Couldn't list deployment {namespace}/{name} pods. Skipping reconcile.")
                    continue

            previous_pods = self.last_emulated_pods.get(workload_key)
            if previous_pods == emulated_pods:
                continue

            self.log(f"[INFO] Emulated pod set changed for {namespace}/{name}. Starting reconciliation.")

            self.reconcile_workload(
                workload_key=workload_key,
                emulated_pods=emulated_pods,
            )

    def reconcile_workload(self, workload_key, emulated_pods=None):
        """
        Reconcile one workload by asking UsageAssignmentEngine for the final
        pod-level assignment and applying it to the cluster.
        """

        namespace, name = workload_key

        last_usage_action = self.last_usage_actions.get(workload_key)

        if emulated_pods is None:
            try:
                emulated_pods = self.list_emulated_pods(namespace, name)
            except ApiException as e:
                if e.status == 404:
                    self.log(f"[INFO] Workload disappeared: {namespace}/{name}")
                    self.cleanup_workload(workload_key)
                    return
                else:
                    self.log(f"[WARNING] Couldn't list deployment {namespace}/{name} pods. Skipping reconcile.")
                    return

        self.last_emulated_pods[workload_key] = emulated_pods

        self.log(
            f"[INFO] Reconciling {namespace}/{name}. "
            f"Real pods: {len(last_usage_action)}. "
            f"Emulated pods: {len(emulated_pods)}."
        )

        assignment = self.assignment_engine.resolve(
            workload_key=workload_key,
            real_pods_usage=last_usage_action,
            emulated_pods=emulated_pods,
        )

        self.apply_assignment(workload_key, assignment)

    # --------------------------------------------------
    # Kubernetes pod discovery
    # --------------------------------------------------
    def list_emulated_pods(self, namespace, workload_name):
        """
        Return the exact set of live emulated pods for a workload.
        """

        pods = self.k8s_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"deployment={workload_name}",
        )

        result = set()
        for pod in pods.items:
            pod_name = pod.metadata.name

            if pod.metadata.deletion_timestamp is not None:
                continue

            phase = pod.status.phase
            if phase in {"Succeeded", "Failed"}:
                continue

            result.add((namespace, pod_name))

        return result

    # --------------------------------------------------
    # Apply assignment
    # --------------------------------------------------

    def apply_assignment(self, workload_key, assignment):
        """
        Apply usage assignment to KWOK.
        """

        namespace, workload_name = workload_key

        desired_crus = set()

        for pod_key, usage in assignment.items():
            pod_namespace, pod_name = pod_key

            cpu = str(usage.get("cpu"))
            memory = f'Quantity("{usage.get("memory")}Gi")' 
            cru_name = f"usage-{pod_namespace}-{pod_name}"
            
            desired_crus.add(cru_name)

            body = self.cru_generator.generate_cluster_resource_usage(
                cru_name=cru_name,
                namespace=pod_namespace,
                pod_name=pod_name,
                container=workload_name,
                cpu=cpu,
                memory=memory,
            )

            self.apply_cru(cru_name, body)

            self.log(
                f"[INFO] Applied usage for {pod_namespace}/{pod_name}: "
                f"cpu={cpu}, memory={memory}"
            )

        self.delete_stale_crus(workload_key, desired_crus)
        self.managed_crus_by_workload[workload_key] = desired_crus

    def apply_cru(self, cru_name, body):
        """
        Create or patch a ClusterResourceUsage object.
        """

        if cru_name in self.existing_crus:
            self.k8s_api.patch_cluster_custom_object(
                group=self.CRU_GROUP,
                version=self.CRU_VERSION,
                plural=self.CRU_PLURAL,
                name=cru_name,
                body=body,
            )
        else:
            self.k8s_api.create_infrastructure_object(
                body=body,
                group=self.CRU_GROUP,
                version=self.CRU_VERSION,
                plural=self.CRU_PLURAL,
            )
            self.existing_crus.add(cru_name)
    
    def delete_cru(self, cru_name):
        """
        Delete a ClusterResourceUsage object.
        """
        
        try:
            self.k8s_api.delete_cluster_custom_object(
                group=self.CRU_GROUP,
                version=self.CRU_VERSION,
                plural=self.CRU_PLURAL,
                name=cru_name,
            )
            self.log(f"[INFO] Deleted CRU {cru_name}")
                     
        except ApiException as e:
            if e.status != 404:
                self.log(f"[WARNING] Failed to delete CRU {cru_name}: {e}") 
                return
        
        self.existing_crus.discard(cru_name)

    def delete_stale_crus(self, workload_key, desired_crus):
        """
        Delete CRUs previously managed for this workload that are no longer
        needed after a pod-set change.
        """

        previous_crus = self.managed_crus_by_workload.get(workload_key, set())
        stale_crus = previous_crus - desired_crus

        for cru_name in stale_crus:
            self.delete_cru(cru_name)

    def cleanup_workload(self, workload_key):
        """
        Remove all local state and CRUs for a workload.
        """
        for cru_name in self.managed_crus_by_workload.get(workload_key, set()):
            self.delete_cru(cru_name)

        self.last_usage_actions.pop(workload_key, None)
        self.last_emulated_pods.pop(workload_key, None)
        self.managed_crus_by_workload.pop(workload_key, None)
