import pandas as pd

class UsageWorkloadActionGenerator:
    """
    A class responsible for generating Kubernetes Node objects,
    particularly for use with Kwok, based on instance data.
    """
    # Default versions and names as per the target YAML

    def __init__(self):
        """
        Initializes the NodeGenerator.
        """
        pass

    def generate_usage_workload_action(self, group: pd.DataFrame) -> list:
        usage_workload_actions = []

        for _, row in group.iterrows():

            name = row['replicaset']
            namespace = row['namespace']
            memory = row['memory_usage']
            cpu = row['cpu_usage']
            container = row['replicaset']

            usage_workload_action = {
                "name": name,
                "namespace": namespace,
                "action": "set-usage",
                "kind": "deployment",
                "memory": memory,
                "cpu": cpu,
                "container": container
            }
            usage_workload_actions.append(usage_workload_action)

        return usage_workload_actions