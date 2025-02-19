import json
import time
import os
from datetime import datetime
from kubernetes import client
from util.k8s_api.k8s_api import K8SAPI

TRACE_STEP = 600

k8s_api = K8SAPI()

with open('/tmp/output_objects.json', 'r') as file:
    data = json.load(file)

def namespace_exists(namespace):
    try:
        k8s_api.read_namespace(name=namespace)
        return True
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return False
        raise

def create_namespace_if_not_exists(namespace):
    if not namespace_exists(namespace):
        body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
        k8s_api.create_namespace(body=body)
        print(f"Namespace {namespace} criado.")
    else:
        print(f"Namespace {namespace} já existe.")

def delete_path_if_exists(yaml_path):
    """Remove o arquivo se ele existir no caminho fornecido."""
    if os.path.exists(yaml_path):
        os.remove(yaml_path)
        print(f"{yaml_path} foi excluído com sucesso.")

def apply_object(obj):
    kind = obj.get("kind", "").lower()
    namespace = obj["metadata"].get("namespace", "default")
    name = obj["metadata"]["name"]

    if kind == "deployment":
        try:
            k8s_api.read_namespaced_deployment(name, namespace)
            k8s_api.patch_namespaced_deployment(name, namespace, obj)
            print(f"Atualizado Deployment {name} no namespace {namespace}")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                k8s_api.create_namespaced_deployment(namespace, obj)
                print(f"Criado Deployment {name} no namespace {namespace}")

    elif kind == "nodeclaim":
        try:
            existing_nodeclaim = k8s_api.get_cluster_custom_object("karpenter.sh", "v1", "nodeclaims", name)
            obj["metadata"].pop("resourceVersion", None)
            k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodeclaims", name, obj)
            print(f"Atualizado NodeClaim {name}")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                obj["metadata"].pop("resourceVersion", None)
                k8s_api.create_cluster_custom_object("karpenter.sh", "v1", "nodeclaims", obj)
                print(f"Criado NodeClaim {name}")

def exec_setup(setup):
    for nodeclaim in setup['nodeclaims']:
        apply_object(nodeclaim)

    for namespace, pods in setup['deployments'].items():
        create_namespace_if_not_exists(namespace)
        for pod in pods:
            apply_object(pod)

def exec_trace(trace):
    current_timestamp = trace[0]["timestamp"]
    start = datetime.now()
    time.sleep(TRACE_STEP)

    for entry in trace:
        entry_timestamp = entry['timestamp']
        if entry_timestamp > current_timestamp:
            time.sleep(entry_timestamp - current_timestamp)
            current_timestamp = entry_timestamp

        # Aplicar novos objetos
        for namespace, objects in entry['applied_objects'].items():
            create_namespace_if_not_exists(namespace)
            for obj in objects:
                apply_object(obj)

        # Processar escalonamento de réplicas
        for obj in entry['scaled_replicasets']:
            name, namespace, replicas, kind = obj['name'], obj['namespace'], obj['pods'], obj['kind']
            if kind == "deployment":
                k8s_api.patch_namespaced_deployment_scale(name, namespace, {"spec": {"replicas": replicas}})
            elif kind == "statefulset":
                k8s_api.patch_namespaced_stateful_set_scale(name, namespace, {"spec": {"replicas": replicas}})
            print(f"Escalado {kind} {name} para {replicas} réplicas no namespace {namespace}")

        # Deletar objetos
        for obj in entry['deleted_objects']:
            name, namespace = obj['name'], obj['namespace']
            k8s_api.delete_namespaced_deployment(name, namespace)
            print(f"Deployment {name} deletado no namespace {namespace}")

    duration = int((datetime.now() - start).total_seconds() + 15)
    os.system(f"python3 collector.py {duration} 30")

# Obtendo NodePools
all_nodepools = [
    item["metadata"]["name"]
    for item in k8s_api.list_cluster_custom_object("karpenter.sh", "v1", "nodepools")["items"]
]

first_disruption_time = {np: k8s_api.get_cluster_custom_object("karpenter.sh", "v1", "nodepools", np)["spec"]["disruption"]["consolidateAfter"] for np in all_nodepools}
new_disruption_time = {np: "6000m" for np in all_nodepools}

# Atualizando tempo de interrupção
for nodepool, time_value in new_disruption_time.items():
    patch = {"spec": {"disruption": {"consolidateAfter": time_value}}}
    k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", nodepool, patch)

exec_setup(data['setup'])

# Executando scripts externos
os.system("python3 pods_mapping.py")
os.system("bash build-scheduler.sh")

# Restaurando tempo de interrupção original
for nodepool, time_value in first_disruption_time.items():
    patch = {"spec": {"disruption": {"consolidateAfter": time_value}}}
    k8s_api.patch_cluster_custom_object("karpenter.sh", "v1", "nodepools", nodepool, patch)

exec_trace(data['trace'])
