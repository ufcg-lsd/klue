import json
import subprocess
import time
import yaml
import os
from datetime import datetime

TRACE_STEP = 600

# Carregando o JSON (substitua pelo caminho do arquivo JSON real)
with open('/tmp/output_objects.json', 'r') as file:
    data = json.load(file)

# Função para verificar se o namespace existe
def namespace_exists(namespace):
    result = subprocess.run(['kubectl', 'get', 'namespace', namespace], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

# Função para criar o namespace se ele não existir
def create_namespace_if_not_exists(namespace):
    if not namespace_exists(namespace):
        subprocess.run(['kubectl', 'create', 'namespace', namespace])
        print(f"Namespace {namespace} criado.")
    else:
        print(f"Namespace {namespace} já existe.")

def delete_path_if_exists(yaml_path):
    """Remove o arquivo se ele existir no caminho fornecido."""
    if os.path.exists(yaml_path):
        os.remove(yaml_path)
        print(f"{yaml_path} foi excluído com sucesso.")
    else:
        print(f"{yaml_path} não existe.")

# Função genérica para aplicar um arquivo YAML no Kubernetes
def apply_object(yaml_path):
    subprocess.run(['kubectl', 'apply', '-f', yaml_path])
    print(f"Objeto aplicado a partir de {yaml_path}")

def get_nodeclaim_as_dict(nodeclaim_name):
    result = subprocess.run(
        ["kubectl", "get", "nodeclaim", nodeclaim_name, "-o", "yaml"],
        stdout=subprocess.PIPE,
        text=True
    )
    return yaml.safe_load(result.stdout)

def remove_ip_taint(nodeclaim_name):
    nodeclaim_dict = get_nodeclaim_as_dict(nodeclaim_name)
    taints = nodeclaim_dict["spec"].get("taints", [])
    node_name = nodeclaim_dict["status"].get("nodeName")

    for taint in taints:
        key = taint.get("key")
        effect = taint.get("effect")
        if key and effect and key.startswith("ip-"):
            command = ["kubectl", "taint", "nodes", node_name, f"{key}:{effect}-"]
            subprocess.run(command)

def get_first_timestamp(data):
    return data[0]["timestamp"]

def change_nodepools_disruption_time(new_nodepools_disruption_time):
    for nodepool, time in new_nodepools_disruption_time.items():
        result = subprocess.run(
            [
                "kubectl", "patch", "nodepool", nodepool,
                "--type=merge",
                "-p", f'{{"spec":{{"disruption":{{"consolidateAfter":"{time}"}}}}}}'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        ).stdout.strip()

def get_disruption_time(nodepool_name):
    result = subprocess.run(
        ["kubectl", "get", "nodepool", nodepool_name, "-o", "jsonpath={.spec.disruption.consolidateAfter}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        ).stdout.strip()
    return result

# Função para rodar o setup inicial
def exec_setup(setup):
    # Aplicando nodeclaims
    nodeclaims_path = f'/tmp/all_nodeclaims.yaml'
    for nodeclaim in setup['nodeclaims']:
        with open(nodeclaims_path, 'a') as f:
            yaml.dump(nodeclaim, f, default_flow_style=False)
            f.write("---\n")
    apply_object(nodeclaims_path)

    # Aplicando deployments
    for namespace in setup['deployments']:
        create_namespace_if_not_exists(namespace)
        yaml_path = f'/tmp/{namespace}_setup.yaml'
        for pod in setup['deployments'][namespace]:
            with open(yaml_path, 'a') as f:
                yaml.dump(pod, f, default_flow_style=False)
                f.write("---\n")
        apply_object(yaml_path)

# Função para executar o trace, aplicando e deletando pods conforme o timestamp
def exec_trace(trace):
    step = 30
    current_timestamp = get_first_timestamp(trace)
    start = datetime.now()
    time.sleep(TRACE_STEP)

    for entry in trace:
        entry_timestamp = entry['timestamp']
        if entry_timestamp > current_timestamp:
            print(f"Vou dormir {entry_timestamp - current_timestamp} segundos")
            time.sleep(entry_timestamp - current_timestamp)
            current_timestamp = entry_timestamp

        # Processando applied_objects
        for namespace in entry['applied_objects']:
            create_namespace_if_not_exists(namespace)
            yaml_path = f'/tmp/{namespace}_execution.yaml'
            delete_path_if_exists(yaml_path)
            for object in entry['applied_objects'][namespace]:
                with open(yaml_path, 'a') as f:
                    yaml.dump(object, f, default_flow_style=False)
                    f.write("---\n")
            apply_object(yaml_path)

        # Processando scaled_replicasets
        for object in entry['scaled_replicasets']:
            name = object['name']
            namespace = object['namespace']
            pods = object['pods']
            kind = object['kind']
            # Esse if é só para não executar scalling dos daemonsets, statefulsets e jobs
            if kind == 'deployment' or kind ==  'statefulset':
                # kubectl scale <tipo-do-recurso>/<nome> --replicas=<quantidade> -n <namespace>
                subprocess.run(['kubectl', 'scale', f'deployment/{name}', f'--replicas={pods}', '-n', namespace])
                print(f"Replicaset {name} sofreu operação de scalling para {pods} no namespace {namespace}")

        # Processando deleted_objects
        for object in entry['deleted_objects']:
            pod_name = object['name']
            namespace = object['namespace']
            subprocess.run(['kubectl', 'delete', 'deployment', pod_name, '-n', namespace])
            print(f"Deployment {pod_name} deletado no namespace {namespace}")

    duration = int((datetime.now() - start).total_seconds() + 15)
    port_forward = subprocess.Popen(["bash", "port-forward.sh"])
    time.sleep(10)
    collector = subprocess.Popen(['python3', 'collector.py', f"{duration}", f"{step}"])

all_nodepools = subprocess.run(
    ["kubectl", "get", "nodepools", "-o", "custom-columns=NAME:.metadata.name", "--no-headers"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    ).stdout.strip().split("\n")

first_disruption_time = {}
new_disruption_time = {}

for nodepool in all_nodepools:
    first_disruption_time[nodepool] = get_disruption_time(nodepool)
    new_disruption_time[nodepool] = "6000m"

change_nodepools_disruption_time(new_disruption_time)
exec_setup(data['setup'])
subprocess.run(["python3", "pods_mapping.py"])
subprocess.run(["bash", "build-scheduler.sh"])
change_nodepools_disruption_time(first_disruption_time)
exec_trace(data['trace'])
