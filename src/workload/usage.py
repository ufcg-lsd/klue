import multiprocessing
import queue
from kubernetes.client.rest import ApiException

from util.k8s_api.k8s_api import K8SAPI
from util.k8s_objects.cluster_resource_usage_generator import ClusterResourceUsageGenerator


class UsageManager(multiprocessing.Process):

    TIME_OUT = 200
    CRU_GROUP = "kwok.x-k8s.io"
    CRU_VERSION = "v1alpha1"
    CRU_PLURAL = "clusterresourceusages"

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

        # container → index mapping inside CRU
        self.container_usage_map = {}

        # deployments with usage registered
        self.deployments = {}

    def log(self, message):
        print(f"[USAGE MANAGER] {message}", flush=True)

    def run(self):

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
                # periodic reconciliation
                self.reconcile_deployments()

    # --------------------------------------------------
    # Kubernetes helpers
    # --------------------------------------------------

    def get_current_replicas(self, namespace, name):
        try:
            deployment = self.k8s_api.read_namespaced_deployment(name, namespace)

            replicas = deployment.status.ready_replicas
            if replicas is None:
                replicas = 1

            return replicas

        except Exception as e:
            self.log(f"[WARNING] Failed to fetch replicas for {name}: {e}")
            return 1

    # --------------------------------------------------
    # Event processing
    # --------------------------------------------------

    def apply_usage(self, event):

        name = event["name"]
        namespace = event["namespace"]
        container = event["container"]

        base_cpu = event["cpu"]
        base_memory = event["memory"]

        cru_name = f"{namespace}-{name}"

        self.log(f"Applying usage -> CRU: {cru_name}, container: {container}")

        # register deployment usage
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

        if cru_name not in self.container_usage_map:
            self.initialize_cru(cru_name, namespace, name, container, cpu, memory)

        container_map = self.container_usage_map[cru_name]

        if container in container_map:
            self.update_container_usage(cru_name, container_map[container], cpu, memory)
        else:
            self.insert_container_usage(cru_name, usage_obj, container)

    # --------------------------------------------------
    # CRU initialization
    # --------------------------------------------------

    def initialize_cru(self, cru_name, namespace, replicaset, container, cpu, memory):

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

        self.log(f"Inserting container usage into {cru_name}")

        # pegar CRU atual
        cru = self.k8s_api.get_cluster_custom_object(
            group=self.CRU_GROUP,
            version=self.CRU_VERSION,
            plural=self.CRU_PLURAL,
            name=cru_name
        )

        usages = cru["spec"].get("usages", [])

        # adicionar novo usage
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

        self.log(f"Updating usage index {index} in {cru_name}")

        # pegar CRU atual
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

        for cru_name, data in self.deployments.items():

            namespace = data["namespace"]
            name = data["name"]

            current_replicas = self.get_current_replicas(namespace, name)

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