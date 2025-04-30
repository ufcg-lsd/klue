"""
Broker class is responsible for managing Kubernetes resources and orchestrating the setup and execution
of a trace emulation process. It interacts with the Kubernetes API to manage namespaces, deployments,
nodeclaims, and other resources, while also handling custom logic for scaling and disruption times.
"""

import json
import time
import os
import subprocess
from datetime import datetime
from kubernetes import client
from util.k8s_api.k8s_api import K8SAPI
from pods_mapping import PodsMapping
from collector import Collector
class Broker:
    """
    Broker class is responsible for managing Kubernetes resources and orchestrating the setup and execution
    of a trace emulation process. It interacts with the Kubernetes API to manage namespaces, deployments,
    nodeclaims, and other resources, while also handling custom logic for scaling and disruption times.
    Attributes:
        input_step (int): Time step interval for processing trace entries.
        data_path (string): The path of the JSON with the objects that will be applied by broker.
    """
    TIME_OUT = 200
    AMOUNT_OF_REAL_NODES = 1

    def __init__(self, input_step=300, data_path='/tmp/output_objects.json'):
        """
        Initializes the Broker class.
        """
        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.input_step = input_step

        with open(data_path, 'r', encoding="utf-8") as file:
            self.data = json.load(file)

        self.nodeclaims_count = self.count_nodeclaims_in_setup()
        self.node_count = 0
        self.pods_mapping = PodsMapping()
        self.collector = Collector(step=30)

    def log(self, message):
        """
        Logs a message with a "[BROKER]" prefix.
        """
        print(f"[BROKER] {message}")

    def expand_nodepools_disruption_time(self):
        """
        Expands the disruption time for all node pools in the Kubernetes cluster.

        This method retrieves the current disruption times for all node pools and stores
        them in the `self.original_disruption_times` dictionary. It then updates the 
        `consolidateAfter` field of the disruption specification for each node pool to 
        a fixed value of "6000m" (6000 minutes).
        """
        self.original_disruption_times = {
            np["metadata"]["name"]: np["spec"]["disruption"]["consolidateAfter"]
            for np in self.k8s_api.list_cluster_custom_object("karpenter.sh", "v1", "nodepools")["items"]
        }

        for np in self.original_disruption_times:
            patch = {"spec": {"disruption": {"consolidateAfter": "6000m"}}}
            self.k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", np, patch)

    def wait_pods_ready(self):
        """
        Waits until the number of currently running pods matches the expected number of pods.

        This method calculates the expected number of pods based on the deployment specifications
        defined in the `self.data` dictionary. It then continuously checks the current number of
        running pods (excluding specific namespaces) and logs the progress until the expected
        number of pods is reached.

        The method uses a 2-second interval between checks to avoid excessive polling.
        """
        expected_pods = 0

        for i in self.data['setup']['deployments'].keys():
            for j in range(len(self.data['setup']['deployments'][i])):
                expected_pods += self.data['setup']['deployments'][i][j]['spec']['replicas']

        while (current_pods := self.count_pods_excluding_namespaces()) != expected_pods:
            self.log(f"[INFO] Current pods: {current_pods}, Expected: {expected_pods}")
            time.sleep(2)

    def restore_nodepools_disruption_time(self):
        """
        Restores the disruption time for all node pools to their original values.

        This method iterates through the `original_disruption_times` dictionary, which contains
        the original disruption times for each node pool. For each node pool, it sends a patch
        request to the Kubernetes API to update the `consolidateAfter` field in the disruption
        specification of the node pool.
        """
        for nodepool, time_value in self.original_disruption_times.items():
            patch = {"spec": {"disruption": {"consolidateAfter": time_value}}}
            self.k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", nodepool, patch)

    def start_mapping_and_scheduler(self):
        """
        Starts the process of mapping pods and running the scheduler.

        This method performs the following actions:
        1. Executes the `run` method of the `pods_mapping` object to initiate pod mapping.
        2. Runs the `build-scheduler.sh` script using a subprocess call to set up the scheduler.
        """
        self.pods_mapping.run()
        subprocess.run(["bash", "build-scheduler.sh"], check=True)

    def namespace_exists(self, namespace):
        """
        Checks if a Kubernetes namespace exists.
        """
        try:
            self.k8s_api.read_namespace(name=namespace)
            return True
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return False
            raise

    def create_namespace_if_not_exists(self, namespace):
        """
        Ensures that a Kubernetes namespace exists. If the namespace does not exist, it creates it.
        """
        if not self.namespace_exists(namespace):
            body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            self.k8s_api.create_namespace(body=body)
            self.log(f"[INFO] Namespace {namespace} created.")
        else:
            self.log(f"[INFO] Namespace {namespace} already exists.")

    def count_nodeclaims_in_setup(self):
        """
        Counts the number of node claims in the setup data.

        This method retrieves the 'setup' dictionary from the instance's data,
        extracts the 'nodeclaims' list from it, and returns the count of items
        in the list. If 'setup' or 'nodeclaims' is not present, it defaults to
        an empty dictionary or list, respectively.
        """
        setup = self.data.get('setup', {})
        nodeclaims = setup.get('nodeclaims', [])
        return len(nodeclaims)

    def delete_path_if_exists(self, yaml_path):
        """
        Deletes the specified file if it exists.
        """
        if os.path.exists(yaml_path):
            os.remove(yaml_path)
            self.log(f"[INFO] {yaml_path} was sucessfully deleted.")

    def apply_object(self, obj):
        """
        Applies a Kubernetes object to the cluster. This method handles the creation
        or update of specific Kubernetes resources based on their kind.
        """
        kind = obj.get("kind", "").lower()
        namespace = obj["metadata"].get("namespace", "default")
        name = obj["metadata"]["name"]

        if kind == "deployment":
            try:
                self.k8s_api.read_namespaced_deployment(name, namespace)
                self.k8s_api.patch_namespaced_deployment(name, namespace, obj)
                self.log(f"[INFO] Deployment {name} updated in namespace {namespace}.")
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    self.k8s_api.create_namespaced_deployment(namespace, obj)
                    self.log(f"[INFO] Deployment {name} created in namespace {namespace}.")

        elif kind == "nodeclaim":
            try:
                obj["metadata"].pop("resourceVersion", None)
                self.k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodeclaims", name, obj)
                self.log(f"[INFO] Nodeclaim {name} updated")
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    obj["metadata"].pop("resourceVersion", None)
                    self.k8s_api.create_cluster_custom_object("karpenter.sh", "v1", "nodeclaims", obj)
                    self.log(f"[INFO] Nodeclaim {name} created")

    def count_nodeclaims_per_nodepool(self):
        """
        Counts the number of node claims associated with each node pool.

        This method processes the 'nodeclaims' data from the 'setup' dictionary
        and calculates the count of node claims for each node pool. If a node claim
        does not have a specific node pool label, it is categorized under "unknown_nodepool".
        """
        setup = self.data.get('setup', {})
        nodeclaims = setup.get('nodeclaims', [])

        nodepool_counts = {}

        for nodeclaim in nodeclaims:
            nodepool = nodeclaim.get("metadata", {}).get("labels", {}).get("karpenter.sh/nodepool", "unknown_nodepool")
            nodepool_counts[nodepool] = nodepool_counts.get(nodepool, 0) + 1

        return nodepool_counts

    def exec_setup(self):
        """
        Executes the setup process for the broker.

        The setup data is expected to be structured as follows:
        - `setup['nodeclaims']`: A list of node claim objects to be applied.
        - `setup['deployments']`: A dictionary where keys are namespace names and 
          values are lists of pod objects to be applied within those namespaces.

        Logs the node count during the waiting process.
        """
        setup = self.data['setup']
        for nodeclaim in setup['nodeclaims']:
            self.apply_object(nodeclaim)

        while self.nodeclaims_count != self.node_count:
            nodes = self.k8s_api.list_node()
            self.node_count = len(nodes.items) - self.AMOUNT_OF_REAL_NODES
            self.log(f"[INFO] Node count: {self.node_count}")
            time.sleep(2)

        for namespace, pods in setup['deployments'].items():
            self.create_namespace_if_not_exists(namespace)
            for pod in pods:
                self.apply_object(pod)

    def exec_trace(self):
        """
        Executes a trace by applying, scaling, and deleting Kubernetes objects based on the provided trace data.
        The method processes a sequence of trace entries, where each entry contains information about
        objects to be applied, scaled, or deleted in a Kubernetes cluster. It simulates the timing of
        operations based on timestamps in the trace and logs the actions performed.
        Steps:
        1. Reads the trace data and initializes the current timestamp.
        2. Simulates time progression using `time.sleep` based on the difference between consecutive timestamps.
        3. Applies Kubernetes objects and creates namespaces if they do not exist.
        4. Scales deployments or stateful sets to the specified number of replicas.
        5. Runs a port-forwarding script and collects metrics for the duration of the trace.
        6. Deletes Kubernetes objects as specified in the trace.
        """
        trace = self.data['trace']
        current_timestamp = trace[0]["timestamp"]
        start = datetime.now()
        time.sleep(self.input_step)

        for entry in trace:
            entry_timestamp = entry['timestamp']
            if entry_timestamp > current_timestamp:
                time.sleep(entry_timestamp - current_timestamp)
                current_timestamp = entry_timestamp

            for namespace, objects in entry['applied_objects'].items():
                self.create_namespace_if_not_exists(namespace)
                for obj in objects:
                    self.apply_object(obj)

            for obj in entry['scaled_replicasets']:
                name, namespace, replicas, kind = obj['name'], obj['namespace'], obj['pods'], obj['kind']
                if kind == "deployment":
                    self.k8s_api.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": replicas}})
                elif kind == "statefulset":
                    self.k8s_api.patch_namespaced_stateful_set_scale(name, namespace, {"spec": {"replicas": replicas}})
                self.log(f"[INFO] Scaled {kind} {name} to {replicas} replicas in namespace {namespace}")

        duration = int((datetime.now() - start).total_seconds() + 15)

        subprocess.run(["bash", "port-forward.sh"], check=True)

        self.collector.collect(duration=duration)

        for entry in trace:
            for obj in entry['deleted_objects']:
                name, namespace = obj['name'], obj['namespace']
                self.k8s_api.delete_namespaced_deployment(name, namespace)
                self.log(f"[INFO] Deployment {name} deleted from namespace {namespace}")

    def count_pods_excluding_namespaces(self):
        """
        Counts the number of pods in the cluster, excluding those in specific namespaces.

        This method retrieves all pods across all namespaces in the Kubernetes cluster
        and filters out pods that belong to the namespaces specified in the 
        `excluded_namespaces` list. It then returns the total count of the remaining pods.
        """
        excluded_namespaces = ["kube-system", "monitoring"]
        pods = self.k8s_api.list_pod_for_all_namespaces()
        return sum(1 for pod in pods.items if pod.metadata.namespace not in excluded_namespaces)

    def run(self):
        """
        Executes the main workflow of the Broker.

        This method orchestrates the entire lifecycle of the Broker's operation.
        """
        self.log("[INFO] Starting Broker.")
        self.expand_nodepools_disruption_time()
        self.exec_setup()
        self.wait_pods_ready()
        self.start_mapping_and_scheduler()
        self.restore_nodepools_disruption_time()
        self.exec_trace()
