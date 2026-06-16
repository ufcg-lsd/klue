import pandas as pd

class UsageWorkloadActionGenerator:
    """
    Generates workload usage actions by grouping pod-level CPU and memory
    metrics by workload.
    """

    def __init__(self):
        pass

    def generate_usage_workload_action(self, group: pd.DataFrame) -> list:
        """
        Creates a set-usage action for each workload found in the input
        DataFrame.

        Args:
            group: DataFrame containing namespace, workload name, pod,
                cpu_usage, and memory_usage columns.

        Returns:
            List of set-usage action dictionaries.
        """
        usage_workload_actions = []

        grouped_usage = group.groupby(
            ["namespace", "name"],
            sort=True
        )

        for (namespace, name), workload_group in grouped_usage:
            pods = {}

            for _, row in workload_group.iterrows():
                pods[row["pod"]] = {
                    "cpu": row["cpu_usage"],
                    "memory": row["memory_usage"]
                }

            usage_workload_action = {
                "name": name,
                "namespace": namespace,
                "action": "set-usage",
                "pods": pods
            }

            usage_workload_actions.append(usage_workload_action)

        return usage_workload_actions