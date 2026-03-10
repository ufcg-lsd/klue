class ClusterResourceUsageGenerator:
    """
    Generates Kwok ClusterResourceUsage objects.
    """

    def generate_cluster_resource_usage(
        self,
        namespace: str,
        replicaset: str,
        container: str,
        cpu: float,
        memory: float
    ) -> dict:
        """
        Generates a ClusterResourceUsage definition.

        Args:
            namespace (str): Namespace of the workload
            replicaset (str): ReplicaSet name
            containers_usage (list): List with container usage definitions.

            Example:
            [
                {
                    "container": "sidecar",
                    "cpu": "0.5",
                    "memory": "Quantity(\"512Mi\")"
                }
            ]

        Returns:
            dict: ClusterResourceUsage object
        """

        name = f"{namespace}-{replicaset}"

        usages = []

        usages.append({
            "containers": [container],
            "usage": {
                "cpu": {
                    "expression": cpu
                },
                "memory": {
                    "expression": memory
                }
            }
        })

        cluster_resource_usage = {
            "apiVersion": "kwok.x-k8s.io/v1alpha1",
            "kind": "ClusterResourceUsage",
            "metadata": {
                "name": name
            },
            "spec": {
                "selector": {},
                "usages": usages
            }
        }

        return cluster_resource_usage