import pandas as pd

class DeploymentsGenerator:
    def __init__(self):
        pass

    def put_cpu_unity(self, value):
        """
        Converte o valor de CPU para milicores (m) e retorna como string.
        """
        return f"{int(float(value) * 1000)}m"

    def put_memory_unity(self, value):
        """
        Converte o valor de memória de bytes para MiB e retorna como string.
        """
        mebibytes = int(value) // (2 ** 20)
        return f"{mebibytes}Mi"

    def generate_applied_deployments(self, group: pd.DataFrame):
        """
        Gera um dicionário de deployments aplicados com base nas linhas do DataFrame.
        """
        applied_deployments = {}

        for _, row in group[group['action'] == 'create'].iterrows():
            if row["owner_kind"].lower() == 'deployment' or row["owner_kind"].lower() == 'statefulset':
                tolerations = [
                    {
                        "key": f"{row['nodepool']}",
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ]

                affinity = {
                    "nodeAffinity": {
                        "requiredDuringSchedulingIgnoredDuringExecution": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "karpenter.sh/nodepool",
                                            "operator": "In",
                                            "values": [row["nodepool"]],
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }

                labels = {
                    "app": "fake-pod",
                    "deployment": row['replicaset']
                }

                pod_template = {
                    "metadata": {"labels": labels},
                    "spec": {
                        "schedulerName": "custom-scheduler",
                        "affinity": affinity,
                        "tolerations": tolerations,
                        "containers": [
                            {
                                "name": "fake-container",
                                "image": "fake-image",
                                "resources": {
                                    "requests": {}
                                },
                            }
                        ],
                    },
                }

                if row['cpu'] != 'NA':
                    pod_template["spec"]["containers"][0]["resources"]["requests"]["cpu"] = self.put_cpu_unity(row['cpu'])
                if row['memory'] != 'NA':
                    pod_template["spec"]["containers"][0]["resources"]["requests"]["memory"] = self.put_memory_unity(row['memory'])

                deployment = {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {"name": row['replicaset'], "namespace": row['namespace']},
                    "spec": {
                        "replicas": row['pods'],
                        "selector": {"matchLabels": labels},
                        "template": pod_template,
                    },
                }

                if row['namespace'] not in applied_deployments:
                    applied_deployments[row['namespace']] = [deployment]
                else:
                    applied_deployments[row['namespace']].append(deployment)

        return applied_deployments


    def generate_deleted_deployments(self, group: pd.DataFrame):
        """
        Gera uma lista de deployments a serem deletados com base nas linhas do DataFrame.
        """
        deleted_deployments = []

        for _, row in group[group['action'] == 'delete'].iterrows():
            deleted_deployments.append({"name": row['replicaset'], "namespace": row['namespace']})

        return deleted_deployments


    def generate_scaled_deployments(self, group: pd.DataFrame):
        """
        Gera uma lista de replicaset escalados com base nas linhas do DataFrame.
        """
        scaled_deployments = []

        for _, row in group[group['action'] == 'scale'].iterrows():
            scaled_deployments.append({"name": row['replicaset'], "namespace": row['namespace'], "pods": row['pods'], "kind": row['owner_kind'].lower()})

        return scaled_deployments
