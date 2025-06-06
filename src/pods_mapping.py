"""
PodsMapping is a class responsible for mapping Kubernetes pods to nodes in a cluster. 
It provides functionality to fetch cluster nodes, map fake nodes to real nodes, and 
associate pods with their respective nodes. The class interacts with the Kubernetes 
API and processes data to generate mappings that can be used for emulation purposes.
"""
import pandas as pd
from util.k8s_api.k8s_api import K8SAPI

class PodsMapping:
    """
    A class to handle the mapping of Kubernetes pods to nodes for emulation purposes.
    This class provides functionality to map fake nodes to real nodes, associate pods with their owners,
    and generate mappings between emulation pods and real nodes. It interacts with the Kubernetes API
    to fetch information about nodes and pods and uses a CSV file to store and update the pods allocation.
    """
    PODS_ALLOCATION_PATH = "/tmp/pods_allocation.csv"

    def __init__(self, karpenter):
        """
        Initializes the PodsMapping class.

        This constructor sets up the Kubernetes API client by creating an instance
        of the K8SAPI class and assigning it to the `k8s_api` attribute.
        """
        self.k8s_api = K8SAPI()
        self.karpenter = karpenter

    def log(self, message):
        """
        Logs a message with a specific prefix indicating the context of the log.
        """
        print(f"[PODS MAPPING] {message}")

    def get_fake_nodes_dict(self):
        """
        Retrieves a dictionary of fake nodes in the Kubernetes cluster, grouped by their instance type.

        This method fetches the list of nodes in the cluster and filters out real nodes based on a regex pattern.
        It organizes the remaining fake nodes into a dictionary where the keys are instance types, and the values
        are lists of fake nodes with their corresponding node names and node pools.
        """
        self.log("[INFO] Fetching cluster nodes with node pool and instance type.")
        self.log("[INFO] This may take a while, please wait...")

        node_data = {}

        nodes = self.k8s_api.list_node()

        for node in nodes.items:
            node_name = node.metadata.name
            instance_type = node.metadata.labels.get('node.kubernetes.io/instance-type')

            if instance_type not in node_data:
                node_data[instance_type] = []

            node_pool = "none"
            if self.karpenter:
                node_pool = node.metadata.labels.get('karpenter.sh/nodepool')

            if node.metadata.annotations.get("kwok.x-k8s.io/node") == "fake":
                node_data[instance_type].append([node_name, node_pool])

        return node_data

    def get_real_nodes_dict(self):
        """
        Generates a dictionary that maps instance types to their corresponding nodes and node pools.

        This method processes the `pods_allocation` DataFrame to extract unique combinations of 
        nodes, node pools, and instance types. It then organizes this data into a dictionary 
        where the keys are instance types, and the values are lists of [node_name, node_pool] pairs.
        """
        unique_nodes = pd.DataFrame()
        if self.karpenter:
            unique_nodes = self.pods_allocation[["node", "nodepool", "instance_type"]].drop_duplicates()
        else:
            unique_nodes = self.pods_allocation[["node", "instance_type"]].drop_duplicates()

        node_data = {}

        for _, row in unique_nodes.iterrows():
            node_name = row["node"]
            instance_type = row["instance_type"]

            node_pool = "none"
            if self.karpenter:
                node_pool = row["nodepool"]
            if instance_type not in node_data:
                node_data[instance_type] = []
            node_data[instance_type].append([node_name, node_pool])

        return node_data


    def get_owners_with_pods(self):
        """
        Retrieves a mapping of Kubernetes deployment owners to their associated pods.

        This method queries all pods across all namespaces in the Kubernetes cluster
        and organizes them by their deployment owner, as specified in the pod's metadata labels.
        """
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
        """
        Maps fake nodes to real nodes based on their instance types and identifiers.

        This method updates the `pods_allocation` DataFrame by replacing real node names
        with corresponding fake node names. It ensures that each real node has a matching
        fake node in the provided dictionaries. If a match is not found, the program logs
        an error and exits.
        """
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
        """
        Maps emulation pods to real nodes based on the provided replicaset-to-pod mapping.

        This method iterates over the `pods_allocation` DataFrame, which contains information
        about the replicaset, namespace, node, and the number of pods to allocate. For each
        replicaset, it assigns pods to nodes by using the `replicaset_pod_dict` mapping, which
        contains lists of pod names for each replicaset.

        The resulting mapping of pods to nodes is saved as a CSV file at `/tmp/pods_and_nodes_map.csv`
        and returned as a pandas DataFrame.
        """
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
        """
        Executes the Pods Mapping process.
        This method performs the following steps:
        1. Logs the start of the Pods Mapping process.
        2. Reads the pods allocation data from a CSV file specified by `PODS_ALLOCATION_PATH`.
        3. Retrieves dictionaries representing fake and real nodes.
        4. Maps fake nodes to real nodes using the retrieved dictionaries.
        5. Retrieves pod owners and their associated pods.
        6. Maps pods to nodes based on the pod owners.
        """
        self.log("[INFO] Starting Pods Mapping.")
        self.pods_allocation = pd.read_csv(self.PODS_ALLOCATION_PATH)
        
        fake_nodes_dict = self.get_fake_nodes_dict()
        real_nodes_dict = self.get_real_nodes_dict()

        self.map_fake_and_real_nodes(fake_nodes_dict, real_nodes_dict)

        pod_owners = self.get_owners_with_pods()

        self.map_pods_and_nodes(pod_owners)
