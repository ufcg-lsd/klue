import multiprocessing
import queue

from kubernetes.client.rest import ApiException
from kubernetes.utils.quantity import parse_quantity
from util.k8s_api.k8s_api import K8SAPI
from util.k8s_objects.cluster_resource_usage_generator import ClusterResourceUsageGenerator
from workload.usage.usage_assignment import UsageAssignmentEngine


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
                "cpu": usage.get("cpu"),
                "memory": int(usage.get("memory"))
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

            emulated_pods_objects = self.list_emulated_pod_objects(namespace, name)
            if emulated_pods_objects is None:
                self.log(f"[WARNING] Skipping reconciliation for {namespace}/{name}. Could not list emulated pods.")
                continue
            
            emulated_pods = self.list_alive_pod_keys(emulated_pods_objects)
            if not emulated_pods: ## admissible check to avoid unecessary API calls.
                deployment_status = self.deployment_exists(namespace, name)

                if deployment_status is None:
                    self.log(f"[WARNING] Skipping cleanup check for {namespace}/{name}. Could not check deployment existence.")
                    continue

                if deployment_status is False:
                    self.cleanup_workload(workload_key)
                    continue

            previous_pods = self.last_emulated_pods.get(workload_key)
            if previous_pods == emulated_pods:
                continue

            self.log(f"[INFO] Emulated pod set changed for {namespace}/{name}. Starting reconciliation.")

            self.reconcile_workload(
                workload_key=workload_key,
                emulated_pods=emulated_pods,
                emulated_pods_objects=emulated_pods_objects
            )

    def reconcile_workload(self, workload_key, emulated_pods=None, emulated_pods_objects=None):
        """
        Reconcile one workload by asking UsageAssignmentEngine for the final
        pod-level assignment and applying it to the cluster.
        """

        namespace, name = workload_key

        last_usage_action = self.last_usage_actions.get(workload_key)

        if emulated_pods is None:
            emulated_pods_objects = self.list_emulated_pod_objects(namespace, name)
            
            if emulated_pods_objects is None:
                self.log(f"[WARNING] Skipping reconciliation for {namespace}/{name}. Could not list emulated pods.")
                return
            
            emulated_pods = self.list_alive_pod_keys(emulated_pods_objects)

            if not emulated_pods: ## admissible check to avoid unecessary API calls.
                deployment_status = self.deployment_exists(namespace, name)

                if deployment_status is None:
                    self.log(f"[WARNING] Skipping cleanup check for {namespace}/{name}. Could not check deployment existence.")
                    return

                if deployment_status is False:
                    self.cleanup_workload(workload_key)
                    return

        self.last_emulated_pods[workload_key] = emulated_pods

        emulated_pods_limit = self.get_pod_limits_map(emulated_pods_objects)

        self.log(
            f"[INFO] Reconciling {namespace}/{name}. "
            f"Real pods: {len(last_usage_action)}. "
            f"Emulated pods: {len(emulated_pods)}."
        )

        assignment = self.assignment_engine.resolve(
            workload_key=workload_key,
            real_pods_usage=last_usage_action,
            emulated_pods_limit=emulated_pods_limit,
            emulated_pods=emulated_pods,
        )

        self.apply_assignment(workload_key, assignment)

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
            memory = f'Quantity("{int(round(usage.get("memory")))}")' 
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

            self.log(
                f"[INFO] Applying usage for {pod_namespace}/{pod_name}: "
                f"cpu={cpu}, memory={memory}"
            )
            self.apply_cru(cru_name, body)

        self.delete_stale_crus(workload_key, desired_crus)
        self.managed_crus_by_workload[workload_key] = desired_crus

    # --------------------------------------------------
    # K8s API calls
    # --------------------------------------------------

    def apply_cru(self, cru_name, body):
        """
        Create or patch a ClusterResourceUsage object.
        """

        try:
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

        except Exception as e:
            self.log(f"[WARNING] Failed to apply usage for CRU {cru_name}: error={e}")

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
            self.existing_crus.discard(cru_name)

        except ApiException as e:
            if e.status == 404:  # if 404, then CRU already no longer exists
                self.existing_crus.discard(cru_name)
            else:
                self.log(f"[WARNING] Failed to delete CRU {cru_name}: {e}") 


        except Exception as e:
            self.log(f"[WARNING] Failed to delete CRU {cru_name}: {e}")

    def list_emulated_pod_objects(self, namespace, workload_name):
        """
        Return the exact set of live emulated pods for a workload.
        """

        try:
            return self.k8s_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"deployment={workload_name}",
            )
        except Exception as e:
            self.log(f"[WARNING] Failed to list emulated pods for {namespace}/{workload_name}: {e}")
            return None

    def deployment_exists(self, namespace, name):
        try:
            self.k8s_api.read_namespaced_deployment(
                namespace=namespace,
                name=name,
            )
            return True

        except ApiException as e:
            if e.status == 404:
                return False
            
            self.log(f"[WARNING] Failed to check deployment {namespace}/{name}: status={e.status}, reason={e.reason}")
            return None
    
        except Exception as e:
            self.log(f"[WARNING] Failed to check deployment {namespace}/{name}: error={e}")
            return None
    # --------------------------------------------------
    # Get emulated pod's useful information
    # --------------------------------------------------

    def is_live_pod(self, pod):
        if pod.metadata.deletion_timestamp is not None:
            return False

        if pod.status.phase in {"Succeeded", "Failed"}:
            return False

        return True
    
    def list_alive_pod_keys(self, pods):
        result = set()
        for pod in pods.items:
            if self.is_live_pod(pod):
                pod_name = pod.metadata.name
                pod_namespace = pod.metadata.namespace

                result.add((pod_namespace, pod_name))
        
        return result

    def get_pod_limits_map(self, pods):
        """
        Return current resource limits for the pods of a workload.
        """

        result = {}

        for pod in pods.items:
            if not self.is_live_pod(pod):
                continue

            namespace = pod.metadata.namespace
            pod_name = pod.metadata.name

            cpu_total = None
            memory_total = None

            for container in pod.spec.containers:
                resources = container.resources
                limits = resources.limits if resources and resources.limits else {}

                cpu_limit_base = limits.get("cpu")
                memory_limit_base = limits.get("memory")

                if cpu_limit_base is not None:
                    cpu_limit = parse_quantity(str(cpu_limit_base))
                    cpu_total = (cpu_total or 0) + cpu_limit

                if memory_limit_base is not None:
                    memory_limit = parse_quantity(str(memory_limit_base))
                    memory_total = (memory_total or 0) + memory_limit

            pod_limits = {}

            if cpu_total is not None:
                pod_limits["cpu"] = float(cpu_total)

            if memory_total is not None:
                pod_limits["memory"] = int(memory_total)

            result[(namespace, pod_name)] = pod_limits

        return result

    # --------------------------------------------------
    # Clean-up
    # --------------------------------------------------

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
        Remove all related state and CRUs for a workload.
        """
        for cru_name in self.managed_crus_by_workload.get(workload_key, set()):
            self.delete_cru(cru_name)

        self.last_usage_actions.pop(workload_key, None)
        self.last_emulated_pods.pop(workload_key, None)
        self.managed_crus_by_workload.pop(workload_key, None)
        self.assignment_engine.cleanup_workload(workload_key)
