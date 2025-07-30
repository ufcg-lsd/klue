"""
DeploymentsGenerator is a utility class for generating Kubernetes deployment objects
based on input data from a pandas DataFrame. It provides methods to create, delete,
and scale deployments, as well as to format CPU and memory resource values.
Converts the CPU value to millicores (m) and returns it as a string.
"""
import pandas as pd

class DeploymentsGenerator:
    def __init__(self, karpenter=True, cluster_autoscaler=False):
        self.karpenter = karpenter
        self.cluster_autoscaler = cluster_autoscaler

    def put_cpu_unity(self, value):
        """
        Converts the CPU value to millicores (m) and returns it as a string.
        """
        return f"{int(float(value) * 1000)}m"

    def put_memory_unity(self, value):
        """
        Converts the memory value from bytes to MiB and returns it as a string.
        """
        mebibytes = int(value) // (2 ** 20)
        return f"{mebibytes}Mi"
    
    def topology_spread_rule(self, spec, labels):
        required = spec.get("required", True)
        max_skew = spec.get("max_skew", 1)

        if required:
            rule_type = "DoNotSchedule"
        else:
            rule_type = "ScheduleAnyway"

        topology_spread = [
                    {
                        "maxSkew": max_skew,
                        "whenUnsatisfiable": rule_type,
                        "labelSelector": {"matchLabels": labels},
                        "topologyKey": "kubernetes.io/hostname",
                    }
                ]
        
        return topology_spread

    def anti_affinity_rule(self, spec, labels):
        required = spec.get("required", True)
        namespace = spec.get("namespace")

        if required:
            rule_type = "requiredDuringSchedulingIgnoredDuringExecution"
            affinity = {
                "podAntiAffinity": {
                    rule_type: [
                        {
                            "labelSelector": {"matchLabels": labels},
                            "namespaces": [namespace],
                            "topologyKey": "kubernetes.io/hostname"
                        }
                    ]
                }
            }
        else:
            rule_type = "preferredDuringSchedulingIgnoredDuringExecution"
            affinity = {
                "podAntiAffinity": {
                    rule_type: [
                        {
                            "weight": 1,
                            "podAffinityTerm": {
                                "labelSelector": {"matchLabels": labels},
                                "namespaces": [namespace],
                                "topologyKey": "kubernetes.io/hostname"
                            }
                        }
                    ]
                }
            }

        return affinity

    def generate_applied_deployments(self, group: pd.DataFrame, rule_spec=None):
        """
        Generates a dictionary of applied deployments based on the rows of the DataFrame.
        """
        if rule_spec:
            rule_type = rule_spec.get("rule_type")
        else:
            rule_type = "no_rule"

        if rule_type == "topology_spread":
            get_rule = self.topology_spread_rule
            rule_name = "topologySpreadConstraints"
        elif rule_type == "anti_affinity":
            get_rule = self.anti_affinity_rule
            rule_name = "affinity"
        elif rule_type == "no_rule":
            rule_name = None
        else:
            raise ValueError(f"Unknown rule: {rule_type}")


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

                if self.cluster_autoscaler:
                    default_toleration_key = "kwok-provider"
                    tolerations = [
                        {
                            "key": default_toleration_key,
                            "operator": "Equal",
                            "value": "true",
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
                elif self.cluster_autoscaler:
                    affinity = {
                        "nodeAffinity": {
                            "requiredDuringSchedulingIgnoredDuringExecution": {
                                "nodeSelectorTerms": [
                                    {
                                        "matchExpressions": [
                                            {
                                                "key": "node-role.kubernetes.io/control-plane",
                                                "operator": "DoesNotExist"
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    }

                labels = {
                    "app": row['replicaset'],
                    "deployment": row['replicaset']
                }

                if rule_name is not None:
                    if rule_type == "anti_affinity":
                        rule_spec['namespace'] = str(row["namespace"])

                    rule = get_rule(rule_spec, labels)

                    extra = {rule_name: rule}
                else:
                    extra = {}

                if "affinity" in extra.keys():
                    extra["affinity"]["nodeAffinity"] = affinity["nodeAffinity"]
                else:
                    extra["affinity"] = affinity


                pod_template = {
                    "metadata": {"labels": labels},
                    "spec": {
                        **({"schedulerName": "custom-scheduler"} if not self.cluster_autoscaler else {}),
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
                        **extra
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
        Generates a list of deployments to be deleted based on the rows of the DataFrame.
        """
        deleted_deployments = []

        for _, row in group[group['action'] == 'delete'].iterrows():
            deleted_deployments.append({"name": row['replicaset'], "namespace": row['namespace']})

        return deleted_deployments


    def generate_scaled_deployments(self, group: pd.DataFrame):
        """
        Generates a list of scaled replicasets based on the rows of the DataFrame.
        """
        scaled_deployments = []

        for _, row in group[group['action'] == 'scale'].iterrows():
            scaled_deployments.append({"name": row['replicaset'], "namespace": row['namespace'], "pods": row['pods'], "kind": row['owner_kind'].lower()})

        return scaled_deployments
