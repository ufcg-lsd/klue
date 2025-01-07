import pandas as pd
from kubernetes import client, config
def list_pods_and_deployments():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    print("Listing pods with their IPs, deployments, and statefulsets:")
    pods = v1.list_pod_for_all_namespaces(watch=False)
    for pod in pods.items:
        owner_name = None
        if pod.metadata.owner_references:
            for ref in pod.metadata.owner_references:
                if ref.kind in ["deployment", "StatefulSet"]:
                    owner_name = ref.name
        print(f"Pod: {pod.metadata.name}, Owner: {owner_name}, Namespace: {pod.metadata.namespace}")
def list_nodes(output_csv_path="nodes_info.csv"):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    print("\nFetching cluster nodes with node pool and instance type:")
    node_data = []
    nodes = v1.list_node()
    for node in nodes.items:
        node_name = node.metadata.name
        node_pool = node.metadata.labels.get('karpenter.sh/nodepool')
        instance_type = node.metadata.labels.get('node.kubernetes.io/instance-type')
        node_data.append({
            "name": node_name,
            "node_pool": node_pool,
            "instance_type": instance_type
        })
    print(len(node_data))
    df = pd.DataFrame(node_data)
    df.to_csv(output_csv_path, index=False)
    return df
def get_owners_with_pods():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    owners_with_pods = {}
    pods = v1.list_pod_for_all_namespaces(watch=False)
    for pod in pods.items:
        owner_name = pod.metadata.labels.get('deployment')
        if owner_name:
            if owner_name not in owners_with_pods:
                owners_with_pods[owner_name] = []
            owners_with_pods[owner_name].append(pod.metadata.name)
    return owners_with_pods
data = pd.read_csv("/home/julia.leal/Tasks/2024Dez/SchedulerInputFile/julia-research/trace-simulation/pods_allocation.csv")
