class UsageAssignmentEngine:

    def __init__(self):
        # (namespace, workload_name) -> {
        #   "mapping": {
        #       (namespace, real_pod_name): (namespace, emulated_pod_name)
        #   },
        #   "last_assignment": {
        #       (namespace, emulated_pod_name): {"cpu": float, "memory": float}
        #   }
        # }
        self.state = {}

    def resolve(self, workload_key, real_pods_usage, emulated_pods):
        """
        Args:
            workload_key:
                (namespace, workload_name)

            real_pods_usage:
                {
                    (namespace, real_pod_name): {
                        "cpu": float,
                        "memory": float
                    }
                }

            emulated_pods:
                {
                    (namespace, emulated_pod_name),
                    ...
                }

        Returns:
            {
                (namespace, emulated_pod_name): {
                    "cpu": float,
                    "memory": float
                }
            }
        """

        state = self.state.setdefault(workload_key, {"mapping": {}, "last_assignment": {}})


        real_pods = set(real_pods_usage.keys())

        # Remove mappings whose real pod or emulated pod no longer exists.
        mapping = {
            real_pod: emulated_pod
            for real_pod, emulated_pod in state["mapping"].items()
            if real_pod in real_pods and emulated_pod in emulated_pods
        }

        unmapped_real_pods = sorted(real_pods - set(mapping.keys()))
        mapped_emulated_pods = set(mapping.values())
        unmapped_emulated_pods = sorted(emulated_pods - mapped_emulated_pods)

        # mapping for newly observed pods.
        for real_pod, emulated_pod in zip(unmapped_real_pods, unmapped_emulated_pods):
            mapping[real_pod] = emulated_pod

        state["mapping"] = mapping

        assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod]

            assignment[emulated_pod] = {
                "cpu": usage["cpu"],
                "memory": usage["memory"],
            }

        state["last_assignment"] = assignment

        return assignment
    
    def cleanup_workload(self, workload_key):
        self.state.pop(workload_key, None)