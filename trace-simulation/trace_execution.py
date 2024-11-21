import json
import subprocess
import time
import yaml
import os

# Carregando o JSON (substitua pelo caminho do arquivo JSON real)
with open('/tmp/output_pods.json', 'r') as file:
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

# Função para rodar o setup inicial
def exec_setup(setup):
    # Aplicando nodeclaims
    nodeclaims_path = f'/tmp/all_nodeclaims.yaml'
    for nodeclaim in setup['nodeclaims']:
        with open(nodeclaims_path, 'a') as f:
            yaml.dump(nodeclaim, f, default_flow_style=False)
            f.write("---\n")
    apply_object(nodeclaims_path)

    # Aplicando pods
    for namespace in setup['pods']:
        create_namespace_if_not_exists(namespace)
        yaml_path = f'/tmp/{namespace}_setup.yaml'
        for pod in setup['pods'][namespace]:
            with open(yaml_path, 'a') as f:
                yaml.dump(pod, f, default_flow_style=False)
                f.write("---\n")
        apply_object(yaml_path)

    # Removendo taints dos nós
    for nodeclaim in setup['nodeclaims']:
        remove_ip_taint(nodeclaim['metadata']['name'])
        print("Taints iniciais de todos os nós foram removidos")

# Função para executar o trace, aplicando e deletando pods conforme o timestamp
def exec_trace(trace):
    current_timestamp = get_first_timestamp(trace)
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
            for pod in entry['applied_objects'][namespace]:
                with open(yaml_path, 'a') as f:
                    yaml.dump(pod, f, default_flow_style=False)
                    f.write("---\n")
            apply_object(yaml_path)

        # Processando deleted_objects
        for obj in entry['deleted_objects']:
            pod_name = obj['name']
            namespace = obj['namespace']
            subprocess.run(['kubectl', 'delete', 'pod', pod_name, '-n', namespace])
            print(f"Pod {pod_name} deletado no namespace {namespace}")

# Iniciando o coletor
collector = subprocess.Popen(['python3', 'trace_collector.py'])
pid = collector.pid

# Execução das funções
exec_setup(data['setup'])

# Bug encontrado, precisamos resolver colocando a feat do tempo inicial do setup
print("Acabei o setup, vou dormir 600 segundos")
time.sleep(600)
exec_trace(data['trace'])

time.sleep(3800)
os.kill(pid, 9)