"""
DeploymentsGenerator is a utility class for generating Kubernetes deployment objects
based on input data from a pandas DataFrame. It provides methods to create, delete,
and scale deployments, as well as to format CPU and memory resource values.
Converts the CPU value to millicores (m) and returns it as a string.
"""
import pandas as pd

class DeploymentsGenerator:
    def __init__(self, karpenter=True):
        self.karpenter = karpenter

    def put_cpu_unity(self, value):
        """
        Returns the CPU value as a string.
        """
        return f"{float(value)}"

    def put_memory_unity(self, value):
        """
        Returns the Memory value as a string.
        """
        return f"{int(value)}"

    def generate_applied_deployments(self, group: pd.DataFrame):
        """
        Generates a dictionary of applied deployments based on the rows of the DataFrame.
        """
        applied_deployments = {}

        for _, row in group[group['action'] == 'create'].iterrows():
            if row["owner_kind"].lower() == 'deployment' or row["owner_kind"].lower() == 'statefulset':
                default_toleration_key = "kwok.x-k8s.io/node" if not self.karpenter else row['nodepool']
                tolerations = [
                    {
                        "key": default_toleration_key,
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                ]

                affinity = {}
                if self.karpenter:
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

                node_selector = {"kwok.x-k8s.io/node": "true"}
                
                pod_template = {
                    "metadata": {"labels": labels},
                    "spec": {
                        "nodeSelector": node_selector,
                        "schedulerName": "custom-scheduler",
                        "affinity": affinity,
                        "tolerations": tolerations,
                        "containers": [
                            {
                                "name": row['replicaset'],
                                "image": "fake-image",
                                "resources": {
                                    "requests": {},
                                    "limits": {}
                                },
                            }
                        ],
                    },
                }

                if pd.notna(row['cpu_request']):
                    pod_template["spec"]["containers"][0]["resources"]["requests"]["cpu"] = self.put_cpu_unity(row['cpu_request'])
                if pd.notna(row['memory_request']):
                    pod_template["spec"]["containers"][0]["resources"]["requests"]["memory"] = self.put_memory_unity(row['memory_request'])

                if pd.notna(row['cpu_limit']):
                    pod_template["spec"]["containers"][0]["resources"]["limits"]["cpu"] = self.put_cpu_unity(row['cpu_limit'])
                if pd.notna(row['memory_limit']):
                    pod_template["spec"]["containers"][0]["resources"]["limits"]["memory"] = self.put_memory_unity(row['memory_limit'])

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
        Generates a list of deployments to be deleted based on the rows of the DataFrame.
        """
        deleted_deployments = []

        for _, row in group[group['action'] == 'delete'].iterrows():
            deleted_deployments.append({"name": row['replicaset'], "namespace": row['namespace'], "kind": row["owner_kind"]})

        return deleted_deployments


    def generate_scaled_deployments(self, group: pd.DataFrame):
        """
        Generates a list of scaled replicasets based on the rows of the DataFrame.
        """
        scaled_deployments = []

        for _, row in group[group['action'] == 'scale'].iterrows():
            scaled_deployments.append({"name": row['replicaset'], "namespace": row['namespace'], "pods": row['pods'], "kind": row['owner_kind'].lower(), "action": "scale"})

        return scaled_deployments
