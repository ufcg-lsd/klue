"""
This module defines the WorkloadManager class, which serves as a base class for managing workloads in a trace emulation environment.
"""

import json
import time
from kubernetes import client
from util.k8s_api.k8s_api import K8SAPI
from util.k8s_object_applier import KubernetesObjectApplier

class WorkloadManager:
    TIME_OUT = 200
    def __init__(self, data_path, emulation_phase):
        """
        Initializes the Workload Manager class.
        """
        self.emulation_phase = emulation_phase

        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.k8s_object_applier = KubernetesObjectApplier(self.k8s_api)

        with open(data_path, 'r', encoding="utf-8") as file:
            self.data = json.load(file)

    def log(self, message):
        """
        Logs a message with a "[WORKLOAD MANAGER]" prefix.
        """
        print(f"[WORKLOAD MANAGER] {message}")

    def before_setup(self):
        pass

    def setup(self):
        """
        Executes the setup process for the broker.

        The setup data is expected to be structured as follows:
        - `setup['nodeclaims']`: A list of node claim objects to be applied.
        - `setup['deployments']`: A dictionary where keys are namespace names and 
          values are lists of pod objects to be applied within those namespaces.

        Logs the node count during the waiting process.
        """
        setup = self.data['setup']

        for namespace, pods in setup.items():
            self.create_namespace_if_not_exists(namespace)
            for pod in pods:
                self.k8s_object_applier.apply_object(pod)

        self.wait_pods_ready()

    def before_emulation(self):
        pass

    def emulation(self):
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
        """
        trace = self.data['emulation']

        emulation_start_wall_clock_time = time.monotonic()
        self.log(f"[INFO] Emulation start time (wall clock): {emulation_start_wall_clock_time:.4f}")

        for entry in trace:
            entry_trace_timestamp = entry["timestamp"]

            # 1. Calculate the target wall clock time for the START of this event
            target_event_start_wall_clock_time = emulation_start_wall_clock_time + entry_trace_timestamp

            # 2. Get the current wall clock time
            current_wall_clock_time = time.monotonic()

            # 3. Calculate how long we need to sleep
            sleep_duration_needed = target_event_start_wall_clock_time - current_wall_clock_time

            if sleep_duration_needed > 0:
                time.sleep(sleep_duration_needed)

            if self.emulation_phase == "dynamic":
                # Apply workload objects
                self.log(f"[INFO] Processing entry at timestamp {entry_trace_timestamp}")
                for namespace, objects in entry.get('applied_objects', {}).items():
                    try:
                        self.create_namespace_if_not_exists(namespace)
                        for obj in objects:
                            self.k8s_object_applier.apply_object(obj)
                    except Exception as e:
                        self.log(f"[ERROR] Failed to apply objects in namespace {namespace}: {e}")

                # Scale workload objects
                for scale_info in entry.get('scaled_replicasets', []):
                    try:
                        name = scale_info['name']
                        namespace = scale_info['namespace']
                        replicas = scale_info['pods']
                        kind = scale_info['kind']

                        if kind == "deployment":
                            self.k8s_api.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": replicas}})
                        elif kind == "statefulset":
                            # For now, we assume that scaling statefulsets is similar to deployments.
                            self.k8s_api.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": replicas}})
                        self.log(f"[INFO] Scaled {kind} {name} to {replicas} replicas in namespace {namespace}")
                    except Exception as e:
                        self.log(f"[ERROR] Failed to scale {kind} {name} in namespace {namespace}: {e}")

                # Delete workload objects
                for delete_info in entry.get('deleted_objects', []):
                    try:
                        name = delete_info['name']
                        namespace = delete_info['namespace']
                        kind = delete_info.get('kind', 'deployment')

                        self.k8s_api.delete_namespaced_deployment(name, namespace)
                        self.log(f"[INFO] Deleted {kind} {name} in namespace {namespace}")
                    except Exception as e:
                        self.log(f"[ERROR] Failed to delete {kind} {name} in namespace {namespace}: {e}")

        # The last timestamp in the trace does not matter (it represents the tear down phase),
        # so we can just sleep for 15 seconds.
        time.sleep(15)

    def tear_down(self):
        pass

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

        for i in self.data['setup'].keys():
            for j in range(len(self.data['setup'][i])):
                expected_pods += self.data['setup'][i][j]['spec']['replicas']

        while (current_pods := self.count_pods_excluding_namespaces()) != expected_pods:
            self.log(f"[INFO] Current pods: {current_pods}, Expected: {expected_pods}")
            time.sleep(2)

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