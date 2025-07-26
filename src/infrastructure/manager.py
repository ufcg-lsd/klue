"""
This module defines the InfrastructureManager class, which manages the setup, emulation, and teardown of Kubernetes infrastructure
for trace-driven experiments. It handles applying Kubernetes objects, managing node pools, and coordinating emulation phases.
"""

import json
import time
from util.k8s_api.k8s_api import K8SAPI
from util.k8s_object_applier import KubernetesObjectApplier

class InfrastructureManager:
    TIME_OUT = 200
    AMOUNT_OF_REAL_NODES = 1

    def __init__(self, data_path, karpenter, emulation_phase, speed_up_factor=None):
        """
        Initializes the Manager class.
        """
        self.karpenter = karpenter
        self.emulation_phase = emulation_phase
        self.speed_up_factor = speed_up_factor

        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.k8s_object_applier = KubernetesObjectApplier(self.k8s_api)

        with open(data_path, 'r', encoding="utf-8") as file:
            self.data = json.load(file)

        self.input_data_node_count = self.count_nodes_in_input_data()
        self.node_count = 0

    def log(self, message):
        """
        Logs a message with a "[INFRASTRUCTURE MANAGER]" prefix.
        """
        print(f"[INFRASTRUCTURE MANAGER] {message}")

    def before_setup(self):
        if self.karpenter == True:
            self.log("[INFO] Expanding nodepools disruption time to 6000 minutes.")
            self.expand_nodepools_disruption_time()

    def setup(self):
        """
        Executes the infrastructure setup process.

        This method applies initial infrastructure configurations from
        `self.data['setup']` to the Kubernetes cluster. These configurations
        are typically expected to be items like custom Node objects or
        NodeClaim-like resources. After applying these objects, the method
        waits until a target number of these managed nodes are observed in
        the cluster.
        """
        setup = self.data['setup']
        for infra_obj in setup:
            self.k8s_object_applier.apply_object(infra_obj)

        while self.input_data_node_count != self.node_count:
            nodes = self.k8s_api.list_node()
            print(f"[INFO] Waiting for nodes to be created. Expected: {self.input_data_node_count}, Current: {len(nodes.items) - self.AMOUNT_OF_REAL_NODES}")
            self.node_count = len(nodes.items) - self.AMOUNT_OF_REAL_NODES
            self.log(f"[INFO] Node count: {self.node_count}")
            time.sleep(2)

    def before_emulation(self):
        """
        Performs pre-emulation setup tasks.

        If Karpenter mode is enabled (self.karpenter is True), this method
        restores the disruption time of nodepools to their original values
        by calling `self.restore_nodepools_disruption_time()`.
        """
        if self.karpenter == True:
            self.log("[INFO] Restoring nodepools disruption time to original values.")
            self.restore_nodepools_disruption_time()

    def emulation(self):
        """
        Executes the main emulation loop based on trace data.

        This method processes a series of time-stamped entries from the trace
        data (`self.data['emulation']`). It aims to synchronize the execution
        of events in the trace with the progression of wall clock time.
        The `entry["timestamp"]` is interpreted as an offset from the start
        of the emulation.

        Key operations:
        1. Records the wall clock time at the start of the emulation.
        2. For each entry in the trace:
           a. Calculates the target wall clock time for the event based on its
              timestamp relative to the emulation start.
           b. Determines the necessary sleep duration to align the current
              wall clock time with the target event time.
           c. Sleeps if needed to simulate the passage of time until the event.
           d. If `self.emulation_phase` is "dynamic":
              i. Applies node objects specified in `entry.get('applied_objects', [])`.
              ii. Deletes nodes specified by name in `entry.get('deleted_objects', [])`,
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

            # 4. If there is a speed-up factor, adjust the sleep duration
            if self.speed_up_factor:
                sleep_duration_needed /= self.speed_up_factor

            if sleep_duration_needed > 0:
                time.sleep(sleep_duration_needed)
            
            if self.emulation_phase == "dynamic":
                for node in entry.get('applied_objects', []):
                    try:
                        self.k8s_object_applier.apply_node(node, node['metadata']['name'])
                    except Exception as e:
                        self.log(f"[ERROR] Failed to apply node {node.get('metadata', {}).get('name', '')}: {e}")

                for node_name in entry.get('deleted_objects', []):
                    try:
                        self.k8s_api.delete_infrastructure_object(node_name)
                        self.log(f"[INFO] Node {node_name} deleted.")
                    except Exception as e:
                        self.log(f"[ERROR] Failed to delete node {node_name}: {e}")

        # The last timestamp in the trace does not matter (it represents the tear down phase),
        # so we can just sleep for the input step duration.
        time.sleep(15)

    def tear_down(self):
        pass

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

    def count_nodes_in_input_data(self):
        """
        Counts the number of node claims in the setup data.

        This method retrieves the 'setup' dictionary from the instance's data,
        extracts the 'nodes' list from it, and returns the count of items
        in the list. If 'setup' or 'nodes' is not present, it defaults to
        an empty dictionary or list, respectively.
        """
        setup_nodes = self.data.get('setup', [])
        return len(setup_nodes)