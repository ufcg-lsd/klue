import multiprocessing
import queue
from kubernetes.client.rest import ApiException

from util.k8s_api.k8s_api import K8SAPI
from util.k8s_objects.cluster_resource_usage_generator import ClusterResourceUsageGenerator


class UsageManager(multiprocessing.Process):
    """
    Background process responsible for managing ClusterResourceUsage (CRU)
    objects used by KWOK to simulate resource usage.

    This manager receives usage events through a queue and updates CRU objects
    accordingly. It also periodically reconciles deployments to detect changes
    in replica count and adjusts per-container resource usage.
    """

    TIME_OUT = 200
    CRU_GROUP = "kwok.x-k8s.io"
    CRU_VERSION = "v1alpha1"
    CRU_PLURAL = "clusterresourceusages"

    def __init__(self, queue):
        """
        Initialize the UsageManager process.

        Args:
            queue: multiprocessing queue used to receive usage events.
        """
        super().__init__()
        self.queue = queue

        # Maps container → index inside CRU.spec.usages
        self.container_usage_map = {}

        # Stores deployments currently tracked for reconciliation
        self.deployments = {}

    def log(self, message):
        """Print formatted log messages for the UsageManager."""
        print(f"[USAGE MANAGER] {message}", flush=True)

    def run(self):
        """
        Main execution loop.

        Waits for events from the queue. When no events arrive within
        the timeout window, a reconciliation loop runs to ensure CRU
        objects remain consistent with the current replica counts.
        """

        self.log("Process started")

        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.cru_generator = ClusterResourceUsageGenerator()

        self.log("K8SAPI initialized")

        while True:

            try:
                event = self.queue.get(timeout=5)

                self.log(f"Event received: {event}")

                if event == "STOP":
                    self.log("Stopping UsageManager")
                    break

                self.apply_usage(event)

            except queue.Empty:
                # No event received → perform periodic reconciliation
                self.reconcile_deployments()

    # --------------------------------------------------
    # Kubernetes helpers
    # --------------------------------------------------

    def get_current_replicas(self, namespace, name):
        """
        Fetch the number of ready replicas for a Deployment.

        Args:
            namespace: Deployment namespace
            name: Deployment name

        Returns:
            int: number of ready replicas (defaults to 1 if unavailable)
        """

        try:
            deployment = self.k8s_api.read_namespaced_deployment(name, namespace)

            replicas = deployment.status.ready_replicas
            if replicas is None:
                replicas = 1

            return replicas

        except Exception as e:
            # Fallback behavior if the Deployment cannot be read
            self.log(f"[WARNING] Failed to fetch replicas for {name}: {e}")
            return 1

    # --------------------------------------------------
    # Event processing
    # --------------------------------------------------

    def apply_usage(self, event):
        """
        Process a usage event and update the corresponding CRU.

        The event describes resource consumption for a container inside a
        deployment. The manager calculates per-replica resource usage and
        updates or inserts entries in the CRU object.

        Args:
            event: dict containing usage data
        """

        name = event["name"]
        namespace = event["namespace"]
        container = event["container"]

        base_cpu = event["cpu"]
        base_memory = event["memory"]

        cru_name = f"{namespace}-{name}"

        self.log(f"Applying usage -> CRU: {cru_name}, container: {container}")

        # Track deployment usage information
        deployment_key = cru_name

        if deployment_key not in self.deployments:
            self.deployments[deployment_key] = {
                "namespace": namespace,
                "name": name,
                "replicas": None,
                "containers": {}
            }

        self.deployments[deployment_key]["containers"][container] = {
            "base_cpu": base_cpu,
            "base_memory": base_memory
        }

        replicas = self.get_current_replicas(namespace, name)
        self.deployments[deployment_key]["replicas"] = replicas

        # Compute per-container usage
        cpu_per_container = round(base_cpu / replicas, 4)
        cpu = str(cpu_per_container)

        memory_mi = (base_memory * 1024) / replicas
        memory_per_container = int(memory_mi)

        memory = f'Quantity("{memory_per_container}Mi")'

        usage_obj = {
            "containers": [container],
            "usage": {
                "cpu": {"expression": cpu},
                "memory": {"expression": memory}
            }
        }

        # Ensure CRU exists
        if cru_name not in self.container_usage_map:
            self.initialize_cru(cru_name, namespace, name, container, cpu, memory)

        container_map = self.container_usage_map[cru_name]

        # Update existing container usage or insert a new one
        if container in container_map:
            self.update_container_usage(cru_name, container_map[container], cpu, memory)
        else:
            self.insert_container_usage(cru_name, usage_obj, container)

    # --------------------------------------------------
    # CRU initialization
    # --------------------------------------------------

    def initialize_cru(self, cru_name, namespace, replicaset, container, cpu, memory):
        """
        Ensure a CRU exists for the given deployment.

        If the CRU already exists, the container index mapping is loaded.
        Otherwise, a new CRU object is created.

        Args:
            cru_name: name of the CRU
            namespace: deployment namespace
            replicaset: deployment name
            container: container name
            cpu: CPU usage expression
            memory: memory usage expression
        """

        self.log(f"Initializing CRU {cru_name}")

        try:

            cru = self.k8s_api.get_cluster_custom_object(
                group=self.CRU_GROUP,
                version=self.CRU_VERSION,
                plural=self.CRU_PLURAL,
                name=cru_name
            )

            usages = cru["spec"].get("usages", [])
            container_map = {}

            # Build container → index mapping
            for i, usage in enumerate(usages):
                for c in usage["containers"]:
                    container_map[c] = i

            self.container_usage_map[cru_name] = container_map

        except ApiException as e:

            if e.status == 404:

                body = self.cru_generator.generate_cluster_resource_usage(
                    namespace,
                    replicaset,
                    container,
                    cpu,
                    memory
                )

                self.k8s_api.create_infrastructure_object(
                    body=body,
                    group=self.CRU_GROUP,
                    version=self.CRU_VERSION,
                    plural=self.CRU_PLURAL
                )

                self.container_usage_map[cru_name] = {container: 0}

                self.log(f"[INFO] Created CRU {cru_name}")

            else:
                raise

    # --------------------------------------------------
    # Insert usage
    # --------------------------------------------------

    def insert_container_usage(self, cru_name, usage_obj, container):
        """
        Insert a new container usage entry into the CRU.

        Args:
            cru_name: CRU name
            usage_obj: usage specification
            container: container name
        """

        self.log(f"Inserting container usage into {cru_name}")

        cru = self.k8s_api.get_cluster_custom_object(
            group=self.CRU_GROUP,
            version=self.CRU_VERSION,
            plural=self.CRU_PLURAL,
            name=cru_name
        )

        usages = cru["spec"].get("usages", [])

        usages.append(usage_obj)

        body = {
            "spec": {
                "usages": usages
            }
        }

        self.k8s_api.patch_cluster_custom_object(
            group=self.CRU_GROUP,
            version=self.CRU_VERSION,
            plural=self.CRU_PLURAL,
            name=cru_name,
            body=body
        )

        index = len(self.container_usage_map[cru_name])
        self.container_usage_map[cru_name][container] = index

        self.log(f"[INFO] Inserted usage for {container} in {cru_name}")

    # --------------------------------------------------
    # Update usage
    # --------------------------------------------------

    def update_container_usage(self, cru_name, index, cpu, memory):
        """
        Update resource usage for an existing container entry in the CRU.

        Args:
            cru_name: CRU name
            index: index inside spec.usages
            cpu: updated CPU expression
            memory: updated memory expression
        """

        self.log(f"Updating usage index {index} in {cru_name}")

        cru = self.k8s_api.get_cluster_custom_object(
            group=self.CRU_GROUP,
            version=self.CRU_VERSION,
            plural=self.CRU_PLURAL,
            name=cru_name
        )

        usages = cru["spec"].get("usages", [])

        container = usages[index]["containers"][0]

        usages[index] = {
            "containers": [container],
            "usage": {
                "cpu": {"expression": cpu},
                "memory": {"expression": memory}
            }
        }

        body = {
            "spec": {
                "usages": usages
            }
        }

        self.k8s_api.patch_cluster_custom_object(
            group=self.CRU_GROUP,
            version=self.CRU_VERSION,
            plural=self.CRU_PLURAL,
            name=cru_name,
            body=body
        )

        self.log(f"[INFO] Updated usage for {container}")

    # --------------------------------------------------
    # Reconciliation loop
    # --------------------------------------------------

    def reconcile_deployments(self):
        """
        Periodically reconcile deployments to detect replica changes.

        If the number of replicas changes, per-container usage is recalculated
        and the CRU object is updated accordingly.

        If a deployment no longer exists, it is removed from the manager state.
        """

        removed = []

        for cru_name, data in self.deployments.items():

            namespace = data["namespace"]
            name = data["name"]

            try:
                deployment = self.k8s_api.read_namespaced_deployment(name, namespace)

                current_replicas = deployment.status.ready_replicas
                if current_replicas is None:
                    current_replicas = 1

            except ApiException as e:

                if e.status == 404:
                    self.log(f"[INFO] Deployment {name} removed")
                    removed.append(cru_name)
                    continue
                else:
                    raise

            if current_replicas == data["replicas"]:
                continue

            self.log(
                f"[INFO] Replica change detected for {name}: "
                f"{data['replicas']} -> {current_replicas}"
            )

            data["replicas"] = current_replicas

            for container, usage in data["containers"].items():

                cpu_per_container = round(usage["base_cpu"] / current_replicas, 4)
                total_cpu = str(cpu_per_container)

                memory_mi = (usage["base_memory"] * 1024) / current_replicas
                memory_per_container = int(memory_mi)

                total_memory = f'Quantity("{memory_per_container}Mi")'

                index = self.container_usage_map[cru_name][container]

                self.update_container_usage(
                    cru_name,
                    index,
                    total_cpu,
                    total_memory
                )

        # Remove deployments that no longer exist
        for cru_name in removed:
            del self.deployments[cru_name]
            self.container_usage_map.pop(cru_name, None)