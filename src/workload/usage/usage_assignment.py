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

        workload_state = self.state.setdefault(workload_key, {"mapping": {}, "last_assignment": {}})
        real_pods = set(real_pods_usage.keys())

        # ----------------------------
        # ===== Updating mapping =====
        # ----------------------------
        # Remove mappings whose real pod or emulated pod no longer exists.
        new_mapping = {
            real_pod: emulated_pod
            for real_pod, emulated_pod in workload_state["mapping"].items()
            if real_pod in real_pods and emulated_pod in emulated_pods
        }

        workload_state["mapping"] = new_mapping

        # mapping for newly observed pods.
        unmapped_real_pods = sorted(real_pods - set(new_mapping.keys()))
        mapped_emulated_pods = set(new_mapping.values())
        unmapped_emulated_pods = sorted(emulated_pods - mapped_emulated_pods)

        n = min(len(unmapped_real_pods), len(unmapped_emulated_pods))
        for real_pod, emulated_pod in zip(unmapped_real_pods, unmapped_emulated_pods):
            new_mapping[real_pod] = emulated_pod
        
        # calling scaling down / scaling up heuristics accordingly
        remaining_real_pods = unmapped_real_pods[n:]
        remaining_emulated_pods = unmapped_emulated_pods[n:]

        if remaining_real_pods:
            assignment = self.homogeneous_spread()
        elif remaining_emulated_pods:
            assignment = self.cdf_sampling_heuristic()
        
        # Creating new pod usage assignment
        # assignment = {}

        # for real_pod, emulated_pod in mapping.items():
        #     usage = real_pods_usage[real_pod]

        #     assignment[emulated_pod] = {
        #         "cpu": usage["cpu"],
        #         "memory": usage["memory"],
        #     }

        workload_state["last_assignment"] = assignment

        return assignment
    
    def homogeneous_spread_heuristic():
        return
    
    def cdf_sampling_heuristic():
        return

    def cleanup_workload(self, workload_key):
        self.state.pop(workload_key, None)