class ClusterResourceUsageGenerator:
    """
    Generates Kwok ClusterResourceUsage objects.
    """

    def generate_cluster_resource_usage(
        self,
        cru_name,
        namespace,
        pod_name,
        container,
        cpu,
        memory,
    ):
        """
        Generate a ClusterResourceUsage with static quantities for exactly one pod.
        """

        return {
            "apiVersion": "kwok.x-k8s.io/v1alpha1",
            "kind": "ClusterResourceUsage",
            "metadata": {
                "name": cru_name,
            },
            "spec": {
                "selector": {
                    "matchNamespaces": [namespace],
                    "matchNames": [pod_name],
                },
                "usages": [
                    {
                        "containers": [container],
                        "usage": {
                            "cpu": {
                                "value": cpu,
                            },
                            "memory": {
                                "value": memory,
                            },
                        },
                    }
                ],
            },
        }
