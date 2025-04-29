import json
import time
import os
from datetime import datetime
from kubernetes import client
from util.k8s_api.k8s_api import K8SAPI
from pods_mapping import PodsMapping
from collector import Collector
import subprocess
class Broker:
    TIME_OUT = 200
    AMOUNT_OF_REAL_NODES = 1

    def __init__(self, input_step=300, data_path='/tmp/output_objects.json'):
        self.k8s_api = K8SAPI(timeout=self.TIME_OUT)
        self.INPUT_STEP = input_step

        with open(data_path, 'r') as file:
            self.data = json.load(file)

        self.nodeclaims_count = self.count_nodeclaims_in_setup()
        self.node_count = 0
        self.pods_mapping = PodsMapping()
        self.collector = Collector(step=30)

    def log(self, message):
        print(f"[BROKER] {message}")
    
    def expand_nodepools_disruption_time(self):
        self.original_disruption_times = {
            np["metadata"]["name"]: np["spec"]["disruption"]["consolidateAfter"]
            for np in self.k8s_api.list_cluster_custom_object("karpenter.sh", "v1", "nodepools")["items"]
        }

        for np in self.original_disruption_times:
            patch = {"spec": {"disruption": {"consolidateAfter": "6000m"}}}
            self.k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", np, patch)
    
    def wait_pods_ready(self):
        expected_pods = 0

        for i in self.data['setup']['deployments'].keys():
            for j in range(len(self.data['setup']['deployments'][i])):
                expected_pods += self.data['setup']['deployments'][i][j]['spec']['replicas']

        while (current_pods := self.count_pods_excluding_namespaces()) != expected_pods:
            self.log(f"[INFO] Current pods: {current_pods}, Expected: {expected_pods}")
            time.sleep(2)

    def restore_nodepools_disruption_time(self):
        for nodepool, time_value in self.original_disruption_times.items():
            patch = {"spec": {"disruption": {"consolidateAfter": time_value}}}
            self.k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", nodepool, patch)
    
    def start_mapping_and_scheduler(self):
        self.pods_mapping.run()
        subprocess.run(["bash", "build-scheduler.sh"])

    def namespace_exists(self, namespace):
        try:
            self.k8s_api.read_namespace(name=namespace)
            return True
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return False
            raise

    def create_namespace_if_not_exists(self, namespace):
        if not self.namespace_exists(namespace):
            body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            self.k8s_api.create_namespace(body=body)
            self.log(f"[INFO] Namespace {namespace} created.")
        else:
            self.log(f"[INFO] Namespace {namespace} already exists.")

    def count_nodeclaims_in_setup(self):
        setup = self.data.get('setup', {})
        nodeclaims = setup.get('nodeclaims', [])
        return len(nodeclaims)

    def delete_path_if_exists(self, yaml_path):
        if os.path.exists(yaml_path):
            os.remove(yaml_path)
            self.log(f"[INFO] {yaml_path} was sucessfully deleted.")

    def apply_object(self, obj):
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
        setup = self.data.get('setup', {})
        nodeclaims = setup.get('nodeclaims', [])

        nodepool_counts = {}

        for nodeclaim in nodeclaims:
            nodepool = nodeclaim.get("metadata", {}).get("labels", {}).get("karpenter.sh/nodepool", "unknown_nodepool")
            nodepool_counts[nodepool] = nodepool_counts.get(nodepool, 0) + 1

        return nodepool_counts

    def exec_setup(self):
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
        trace = self.data['trace']
        current_timestamp = trace[0]["timestamp"]
        start = datetime.now()
        time.sleep(self.INPUT_STEP)

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

        subprocess.run(["bash", "port-forward.sh"])
        
        self.collector.collect(duration=duration)

        for entry in trace:
            for obj in entry['deleted_objects']:
                name, namespace = obj['name'], obj['namespace']
                self.k8s_api.delete_namespaced_deployment(name, namespace)
                self.log(f"[INFO] Deployment {name} deleted from namespace {namespace}")

    def count_pods_excluding_namespaces(self):
        excluded_namespaces = ["kube-system", "monitoring"]
        pods = self.k8s_api.list_pod_for_all_namespaces()
        return sum(1 for pod in pods.items if pod.metadata.namespace not in excluded_namespaces)

    def run(self):
        self.log("[INFO] Starting Broker.")
        self.expand_nodepools_disruption_time()
        self.exec_setup()
        self.wait_pods_ready()
        self.start_mapping_and_scheduler()
        self.restore_nodepools_disruption_time()
        self.exec_trace()