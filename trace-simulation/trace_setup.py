import pandas as pd
import json
import sys
import subprocess
from util.pod import PodGenerator
from util.nodeclaim import NodeClaimGenerator

kube_pod_container_resource_requests_path = sys.argv[1]
karpenter_pods_state_path = sys.argv[2]

# Carregando os arquivos CSV
kube_pod_container_resource_requests = pd.read_csv(kube_pod_container_resource_requests_path)
karpenter_pods_state = pd.read_csv(karpenter_pods_state_path)

pod_generator = PodGenerator()

def sum_ignore_na(series):
    '''
    Function to sum while ignoring 'NA' values, but retaining 'NA' if all entries are 'NA'.
    '''
    if series.isna().all():
        return pd.NA
    return series.sum(skipna=True)

# Identificando as colunas de 'name...2' até 'name...30', excluindo 'name...1'
name_columns = [col for col in karpenter_pods_state.columns if col.startswith('name...') and col not in ['name...1']]

# Consolidando as colunas 'name...2' até 'name...30' em uma única coluna 'pod' com o primeiro valor não-NA
karpenter_pods_state['pod'] = karpenter_pods_state[name_columns].bfill(axis=1).iloc[:, 0]

# Selecionando apenas as colunas finais desejadas
karpenter_pods_state = karpenter_pods_state[['timestamp', 'instance_type', 'node', 'pod', 'nodepool', 'phase']]

# Preenchendo 'nodepool' com 'default' onde houver valores NA
karpenter_pods_state['nodepool'] = karpenter_pods_state['nodepool'].fillna('default')

# Agrupando por pod e namespace no DataFrame e extraindo o menor e maior timestamp
timestamps_resource_requests = kube_pod_container_resource_requests.groupby(["pod", "namespace", "container", "value", "resource"]).agg(
    start_time=('timestamp', 'min'),
    end_time=('timestamp', 'max')
).reset_index()

timestamps_karpenter_pods_state = karpenter_pods_state.groupby(["pod", "nodepool", "instance_type", "node"]).agg(
    start_time=('timestamp', 'min'),
    end_time=('timestamp', 'max')
).reset_index()

# Fazendo o merge com base em pod, namespace
df_merged = pd.merge(
    timestamps_resource_requests, timestamps_karpenter_pods_state,
    on=["pod"], 
    how="left", suffixes=('_kube_pod_container_resource_requests', '_kube_pod_info')
)

# Consolidando as colunas 'start_time' e 'end_time' em uma única coluna cada
df_merged['start_time'] = df_merged['start_time_kube_pod_container_resource_requests'].combine_first(df_merged['start_time_kube_pod_info'])
df_merged['end_time'] = df_merged['end_time_kube_pod_container_resource_requests'].combine_first(df_merged['end_time_kube_pod_info'])

# Removendo as colunas duplicadas após a consolidação
df_merged = df_merged.drop(columns=['start_time_kube_pod_container_resource_requests', 'start_time_kube_pod_info',
                                    'end_time_kube_pod_container_resource_requests', 'end_time_kube_pod_info'])

# Remover linhas duplicadas, mantendo apenas as únicas
df_merged = df_merged.drop_duplicates()

# Usar pivot para transformar 'resource' em colunas separadas para 'cpu' e 'memory'
df_pivoted = df_merged.pivot(index=['pod', 'namespace', 'container', 'nodepool', 'instance_type', 'node', 'start_time', 'end_time'], 
                      columns='resource', 
                      values='value').reset_index()

# Remover o nome do índice das colunas
df_pivoted.columns.name = None

# Somando CPU e memória para cada pod, sem manter a coluna 'container'
df_summed = df_pivoted.groupby(['pod', 'namespace', 'instance_type', 'nodepool', 'node', 'start_time', 'end_time'], as_index=False).agg({
    'cpu': sum_ignore_na,
    'memory': sum_ignore_na,
    'start_time': 'min',  # Mantém o menor start_time
    'end_time': 'max'     # Mantém o maior end_time
})

# Preenchendo valores ausentes com 'NA' para CPU e memória
df_summed['cpu'] = df_summed['cpu'].fillna('NA')
df_summed['memory'] = df_summed['memory'].fillna('NA')

# Removendo pods que são criados e removidos no mesmo timestamp
df_summed = df_summed[df_summed['start_time'] != df_summed['end_time']]

# Removendo pods que são criados e removidos antes de 30 segundos
df_summed = df_summed[(df_summed['end_time'] - 30) >= df_summed['start_time']]

# Criando DataFrames separados para 'create' e 'delete' e concatenando
df_create = df_summed[['pod', 'namespace', 'cpu', 'memory', 'instance_type', 'nodepool', 'node', 'start_time']].copy()
df_create.rename(columns={'start_time': 'timestamp'}, inplace=True)
df_create['action'] = 'create'

df_delete = df_summed[['pod', 'namespace', 'cpu', 'memory', 'instance_type', 'nodepool', 'node', 'end_time']].copy()
df_delete.rename(columns={'end_time': 'timestamp'}, inplace=True)
df_delete['action'] = 'delete'

# Concatenando os DataFrames de 'create' e 'delete'
df_final = pd.concat([df_create, df_delete])

# Ordenando pelo timestamp, depois por 'action' (primeiro 'create', depois 'delete')
df_final['action'] = pd.Categorical(df_final['action'], categories=['create', 'delete'], ordered=True)
df_final.sort_values(by=['timestamp', 'action'], inplace=True)

# Reorganizando as colunas para garantir que 'timestamp' seja a primeira
df_final = df_final[['timestamp', 'pod', 'namespace', 'cpu', 'memory', 'action', 'instance_type', 'nodepool', 'node']]
df_final = df_final[~((df_final['cpu'] == 'NA') | (df_final['memory'] == 'NA'))]

# Contagem total de pods criados e removidos (únicos)
total_pods = df_final['pod'].nunique()
print(f"Total de pods após remover NAs e pods que acabam no primeiro timestamp: {total_pods}")

# Salvando o resultado em um novo arquivo CSV
df_final.to_csv('/tmp/final_trace.csv', index=False)

setup = {'nodeclaims': [], 'pods': []}

first_timestamp = df_final['timestamp'].min()

# Criando JSON a partir do DataFrame df_final
json_output = []
for timestamp, group in df_final.groupby('timestamp'):
    if timestamp == first_timestamp:
        setup['pods'] = pod_generator.get_pods_json(group, node_toleration=True)[0]
    else:
        applied_objects, deleted_objects = pod_generator.get_pods_json(group)

        json_output.append({
            "timestamp": int(timestamp),
            "applied_objects": applied_objects,
            "deleted_objects": deleted_objects
        })

df_filtered = df_final[(df_final['action'] != 'delete') & (df_final['timestamp'] == first_timestamp)]
df_grouped = df_filtered.groupby(['node', 'nodepool', 'instance_type'])

nodeclaim_generator = NodeClaimGenerator()
with open("data/instance_types.json") as f:
    instance_data = json.load(f)

for (node_ip, nodepool_name, instance_name), group in df_grouped:
    nodeclaim = nodeclaim_generator.create_nodeclaim_from_instance(node_ip, instance_name, instance_data, nodepool_name)

    if nodeclaim:
        setup['nodeclaims'].append(nodeclaim)

# Estrutura completa do JSON
final_json_output = {
    "setup": setup,
    "trace": json_output
}

# Convertendo para JSON e salvando no arquivo
json_result = json.dumps(final_json_output, indent=4)
with open('/tmp/output_pods.json', 'w') as f:
    f.write(json_result)
