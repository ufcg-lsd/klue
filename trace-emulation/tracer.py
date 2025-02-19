import os
import pandas as pd
import json
import sys
from util.k8s_object_generator import K8SObjectGenerator

kube_pod_container_resource_requests_path = sys.argv[1]
karpenter_pods_state_path = sys.argv[2]
kube_pod_owner_path = sys.argv[3]
kube_replicaset_owner_path = sys.argv[4]

# Carregando os arquivos CSV
kube_pod_container_resource_requests = pd.read_csv(kube_pod_container_resource_requests_path)
karpenter_pods_state = pd.read_csv(karpenter_pods_state_path)
kube_pod_owner = pd.read_csv(kube_pod_owner_path)
kube_replicaset_owner = pd.read_csv(kube_replicaset_owner_path)

k8s_objects_generator = K8SObjectGenerator()

def sum_ignore_na(series):
    '''
    Function to sum while ignoring 'NA' values, but retaining 'NA' if all entries are 'NA'.
    '''
    if series.isna().all():
        return pd.NA
    return series.sum(skipna=True)

karpenter_pods_state["pod"] = karpenter_pods_state["name.1"]

# Selecionando apenas as colunas finais desejadas
karpenter_pods_state = karpenter_pods_state[['timestamp', 'instance_type', 'node', 'pod', 'nodepool', 'phase']]

# Preenchendo 'nodepool' com 'default' onde houver valores NA
karpenter_pods_state['nodepool'] = karpenter_pods_state['nodepool'].fillna('default')

kube_pod_container_resource_requests = kube_pod_container_resource_requests[["timestamp", "pod", "namespace", "value", "resource", "node"]]

# Merge direto usando 'timestamp' e 'pod' como chaves
df_merged = pd.merge(
    kube_pod_container_resource_requests,
    karpenter_pods_state,
    on=["timestamp", "pod", "node"],
    how="left",
    suffixes=('_resource_requests', '_karpenter_state')
)

# Remover linhas duplicadas, mantendo apenas as únicas
df_merged = df_merged.drop_duplicates()

# Soma todas as ocorrencias de cpu e memoria para cada timestamp de um pod
df_merged = df_merged.groupby(['timestamp', 'pod', 'namespace', 'nodepool', 'instance_type', 'node', 'resource']).agg({
    'value': 'sum'
}).reset_index()

# Usar pivot para transformar 'resource' em colunas separadas para 'cpu' e 'memory'
df_pivoted = df_merged.pivot(index=['timestamp', 'pod', 'namespace', 'nodepool', 'instance_type', 'node'],
                      columns='resource',
                      values='value').reset_index()

# Preenchendo valores ausentes com 'NA' para CPU e memória
df_pivoted['cpu'] = df_pivoted['cpu'].fillna('NA')
df_pivoted['memory'] = df_pivoted['memory'].fillna('NA')

df_final = df_pivoted[~((df_pivoted['cpu'] == 'NA') | (df_pivoted['memory'] == 'NA'))]

# Contagem total de pods criados e removidos (únicos)
total_pods = df_final['pod'].nunique()
print(f"Total de pods após remover NAs e pods que acabam no primeiro timestamp: {total_pods}")

kube_pod_owner = kube_pod_owner.drop_duplicates(subset='pod', keep='first')
kube_replicaset_owner = kube_replicaset_owner.drop_duplicates(subset='replicaset', keep='first')

df_final = pd.merge(df_final, kube_pod_owner[['pod', 'owner_name', 'owner_kind']], on='pod', how='left')

df_final.rename(columns={'owner_name': 'replicaset'}, inplace=True)

df_final = pd.merge(df_final, kube_replicaset_owner[['replicaset', 'owner_kind', 'owner_name']], on='replicaset', how='left')

df_final['owner_kind'] = df_final['owner_kind_y'].combine_first(df_final['owner_kind_x'])

df_final['replicaset'] = df_final['owner_name'].combine_first(df_final['replicaset'])

df_final = df_final.drop(columns=['owner_kind_x', 'owner_kind_y'])

df_final = df_final[~df_final['namespace'].isin(['kube-system'])]

# Removendo DaemonSets e Jobs
df_final = df_final[~df_final['owner_kind'].isin(['DaemonSet', 'Job'])]

print(df_final[df_final['timestamp'] == df_final['timestamp'].min()]['pod'].nunique())

all_nodes = df_final['node'].unique()

all_nodes_df = pd.DataFrame(all_nodes, columns=["node"])

all_nodes_df.to_csv("/tmp/all_nodes.csv", index=False)

df_pods_allocation = df_final[df_final['timestamp'] == df_final['timestamp'].min()]
df_pods_allocation = df_pods_allocation.groupby(['namespace', 'node', 'nodepool', 'replicaset', 'owner_kind', 'instance_type']).agg(
    pods_count=('replicaset', 'count'),
).reset_index()

df_pods_allocation.to_csv("/tmp/pods_allocation.csv", index=False)

df_final = df_final.groupby(['timestamp', 'namespace', 'nodepool', 'replicaset', 'owner_kind']).agg(
    pods_count=('replicaset', 'count'),
    cpu_count=('cpu', 'mean'),
    memory_count=('memory', 'mean')
).reset_index()

df_final = df_final.rename(columns={'pods_count': 'pods', 'cpu_count': 'cpu', 'memory_count': 'memory'})

min_timestamp = df_final['timestamp'].min()

# Essa etapa é para adicionar a ação relacionada ao replicaset
df_final['action'] = 'scale'

first_occurrences = df_final.groupby(['replicaset','nodepool','namespace']).head(1).index
df_final.loc[first_occurrences, 'action'] = 'create'

last_occurrences = df_final.groupby(['replicaset','nodepool','namespace']).tail(1).index
df_final.loc[last_occurrences, 'action'] = 'delete'

df_final['pods_changed'] = df_final.groupby('replicaset')['pods'].diff().fillna(1) != 0

df_final = df_final[df_final['pods_changed'] | (df_final['action'].isin(['create', 'delete']))].drop(columns=['pods_changed'])

df_final.to_csv('/tmp/final_trace.csv', index=False)

setup = {'nodeclaims': [], 'deployments': []}

first_timestamp = df_final['timestamp'].min()

# Criando JSON a partir do DataFrame df_final
json_output = []
for timestamp, group in df_final.groupby('timestamp'):
    if timestamp == first_timestamp:
        setup['deployments'], _, _ = k8s_objects_generator.generate_deployments(group)
    else:
        applied_objects, deleted_objects, scaled_replicasets = k8s_objects_generator.generate_deployments(group)

        json_output.append({
            "timestamp": int(timestamp),
            "applied_objects": applied_objects,
            "deleted_objects": deleted_objects,
            "scaled_replicasets": scaled_replicasets
        })

# Remover duplicatas com base em 'node' e 'instance_type'
df_unique = df_pods_allocation.drop_duplicates(subset=['node', 'instance_type']).reset_index(drop=True)

df_unique.to_csv("/tmp/nodeclaims.csv", index=False)

df_grouped = df_unique.groupby(['node', 'nodepool', 'instance_type'])

with open("data/instance_types.json") as f:
    instance_data = json.load(f)

for (node_ip, nodepool_name, instance_type), group in df_grouped:
    nodeclaim = k8s_objects_generator.generate_nodeclaim(instance_type, instance_data, nodepool_name)

    if nodeclaim:
        setup['nodeclaims'].append(nodeclaim)

# Estrutura completa do JSON
final_json_output = {
    "setup": setup,
    "trace": json_output
}

# Convertendo para JSON e salvando no arquivo
json_result = json.dumps(final_json_output, indent=4)
with open('/tmp/output_objects.json', 'w') as f:
    f.write(json_result)
