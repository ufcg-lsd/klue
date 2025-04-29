import pandas as pd
from util.k8s_api.k8s_api import K8SAPI
import re

class PodsMapping:
    PODS_ALLOCATION_PATH = "/tmp/pods_allocation.csv"

    def __init__(self):
        self.k8s_api = K8SAPI()

    def log(self, message):
        print(f"[PODS MAPPING] {message}")

    def get_fake_nodes_dict(self):
        self.log("[INFO] Fetching cluster nodes with node pool and instance type.")
        self.log("[INFO] This may take a while, please wait...")

        node_data = {}

        nodes = self.k8s_api.list_node()
        real_node_regex = r"^ip-\d{3}-\d{2}-\d{2}-\d{3}\..*"

        for node in nodes.items:
            node_name = node.metadata.name
            node_pool = node.metadata.labels.get('karpenter.sh/nodepool')
            instance_type = node.metadata.labels.get('node.kubernetes.io/instance-type')

            if instance_type not in node_data:
                node_data[instance_type] = []

            if not re.match(real_node_regex, node_name):
                node_data[instance_type].append([node_name, node_pool])

        return node_data

    def get_real_nodes_dict(self):
        unique_nodes = self.pods_allocation[["node", "nodepool", "instance_type"]].drop_duplicates()

        node_data = {}

        for _, row in unique_nodes.iterrows():
            node_name = row["node"]
            node_pool = row["nodepool"]
            instance_type = row["instance_type"]

            if instance_type not in node_data:
                node_data[instance_type] = []
            node_data[instance_type].append([node_name, node_pool])

        return node_data


    def get_owners_with_pods(self):
        owners_with_pods = {}

        pods = self.k8s_api.list_pod_for_all_namespaces()

        for pod in pods.items:
            owner_name = pod.metadata.labels.get('deployment')

            if owner_name:
                if owner_name not in owners_with_pods:
                    owners_with_pods[owner_name] = []
                owners_with_pods[owner_name].append(pod.metadata.name)

        return owners_with_pods

    def map_fake_and_real_nodes(self, fake_nodes_dict, real_nodes_dict):
        self.log("[INFO] Mapping fake nodes to real nodes.")
        for real_instance_type, real_nodes in real_nodes_dict.items():
            if real_instance_type not in fake_nodes_dict:
                self.log(f"[ERROR] Instance type {real_instance_type} not found in the cluster.")
                exit()

            for real_node in real_nodes:
                for fake_node_index, fake_node in enumerate(fake_nodes_dict[real_instance_type]):
                    if fake_node[1] == real_node[1]:
                        self.pods_allocation.loc[self.pods_allocation["node"] == real_node[0], "node"] = fake_node[0]
                        fake_nodes_dict[real_instance_type].pop(fake_node_index)
                        break

                else:
                    self.log(f"[ERROR] No fake node found for the real node: {real_node}")
                    exit()

        self.pods_allocation.to_csv(self.PODS_ALLOCATION_PATH, index=False)

    def map_pods_and_nodes(self, replicaset_pod_dict):
        self.log("[INFO] Mapping emulation pods to real nodes.")
        result_rows = []

        for _, row in self.pods_allocation.iterrows():
            replicaset = row['replicaset']
            pods_count = int(row['pods_count'])

            for _ in range(pods_count):
                if replicaset in replicaset_pod_dict and replicaset_pod_dict[replicaset]:
                    pod_name = replicaset_pod_dict[replicaset].pop(0)

                    result_rows.append({
                        "pod": pod_name,
                        "namespace": row["namespace"],
                        "node": row["node"]
                    })

        result_df = pd.DataFrame(result_rows)
        result_df.to_csv("/tmp/pods_and_nodes_map.csv", index=False)
        return result_df
    
    def run(self):
        self.log("[INFO] Starting Pods Mapping.")
        self.pods_allocation = pd.read_csv(self.PODS_ALLOCATION_PATH)
        
        fake_nodes_dict = self.get_fake_nodes_dict()
        real_nodes_dict = self.get_real_nodes_dict()

        self.map_fake_and_real_nodes(fake_nodes_dict, real_nodes_dict)

        pod_owners = self.get_owners_with_pods()

        self.map_pods_and_nodes(pod_owners)
