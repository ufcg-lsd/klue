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

# Função para executar o trace, aplicando e deletando pods conforme o timestamp
def exec_trace(trace):
    # Iniciando o coletor
    collector = subprocess.Popen(['python3', 'trace_collector.py'])
    pid = collector.pid
    
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

    os.kill(pid, 9)

# Execução das funções
exec_setup(data['setup'])
exec_trace(data['trace'])