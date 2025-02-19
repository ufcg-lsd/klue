import pandas as pd
from util.k8s_api.k8s_api import K8SAPI
import re

PODS_ALLOCATION_PATH = "/tmp/pods_allocation.csv"

pods_allocation = pd.read_csv(PODS_ALLOCATION_PATH)

k8s_api = K8SAPI()

def get_fake_nodes_dict(k8s_api: K8SAPI):
    print("\nFetching cluster nodes with node pool and instance type:")

    node_data = {}

    nodes = k8s_api.list_node()
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

def get_real_nodes_dict(pods_allocation: pd.DataFrame):
    unique_nodes = pods_allocation[["node", "nodepool", "instance_type"]].drop_duplicates()

    node_data = {}

    for _, row in unique_nodes.iterrows():
        node_name = row["node"]
        node_pool = row["nodepool"]
        instance_type = row["instance_type"]

        if instance_type not in node_data:
            node_data[instance_type] = []
        node_data[instance_type].append([node_name, node_pool])
        
    return node_data


def get_owners_with_pods(k8s_api: K8SAPI):
    owners_with_pods = {}

    pods = k8s_api.list_pod_for_all_namespaces()

    for pod in pods.items:
        owner_name = pod.metadata.labels.get('deployment')  

        if owner_name:
            if owner_name not in owners_with_pods:
                owners_with_pods[owner_name] = []  
            owners_with_pods[owner_name].append(pod.metadata.name) 

    return owners_with_pods

def map_fake_and_real_nodes(fake_nodes_dict, real_nodes_dict, pods_allocation):
    print(fake_nodes_dict)
    for real_instance_type, real_nodes in real_nodes_dict.items():
        if real_instance_type not in fake_nodes_dict:
            print(f"Instância {real_instance_type} não foi encontrada no cluster emulado")
            exit()

        for real_node in real_nodes:
            for fake_node_index, fake_node in enumerate(fake_nodes_dict[real_instance_type]):
                if fake_node[1] == real_node[1]:
                    pods_allocation.loc[pods_allocation["node"] == real_node[0], "node"] = fake_node[0]
                    fake_nodes_dict[real_instance_type].pop(fake_node_index)
                    break
            else:
                print(f"Nenhum nó falso encontrado para o nó real: {real_node}")
                exit()

    pods_allocation.to_csv(PODS_ALLOCATION_PATH, index=False)

def map_pods_and_nodes(pods_allocation, replicaset_pod_dict):
    result_rows = []

    for _, row in pods_allocation.iterrows():
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
            else:
                print(f"Nenhum pod restante para replicaset {replicaset}")
                exit()

    result_df = pd.DataFrame(result_rows)
    result_df.to_csv("/tmp/pods_and_nodes_map.csv", index=False)
    return result_df

    
fake_nodes_dict = get_fake_nodes_dict(k8s_api)
real_nodes_dict = get_real_nodes_dict(pods_allocation)

map_fake_and_real_nodes(fake_nodes_dict, real_nodes_dict, pods_allocation)

pod_owners = get_owners_with_pods(k8s_api)

print(pod_owners)

map_pods_and_nodes(pods_allocation, pod_owners)