from workload.usage.heuristics.homogeneous_spread import HomogeneousSpreadHeuristic
from workload.usage.heuristics.cdf_sampling import CDFSamplingHeuristic

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
        self.compression_heuristic_cpu = HomogeneousSpreadHeuristic()
        self.compression_heuristic_mem = HomogeneousSpreadHeuristic()
        self.expansion_heuristic_cpu = CDFSamplingHeuristic()
        self.expansion_heuristic_mem = CDFSamplingHeuristic()

    def resolve(self, workload_key, real_pods_usage, emulated_pods_limit, emulated_pods):
        """
        Args:
            workload_key:
                (namespace, workload_name)

            real_pods_usage and emulated_pods_limit:
                {
                    (namespace, pod_name): {
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
        
        # calling scaling down / scaling up accordingly
        remaining_real_pods = unmapped_real_pods[n:]
        remaining_emulated_pods = unmapped_emulated_pods[n:]

        if remaining_real_pods:
            cpu_assignment = self.compression_heuristic_cpu.generate_assignment(
                real_pods_usage,
                emulated_pods_limit, 
                emulated_pods, 
                new_mapping,
                remaining_real_pods,
                resource="cpu"
            )

            mem_assignment = self.compression_heuristic_mem.generate_assignment(
                real_pods_usage,
                emulated_pods_limit, 
                emulated_pods, 
                new_mapping, 
                remaining_real_pods,
                resource="memory"
            )

        elif remaining_emulated_pods:
            cpu_assignment = self.expansion_heuristic_cpu.generate_assignment(
                real_pods_usage,
                emulated_pods, 
                new_mapping,
                remaining_emulated_pods,
                resource="cpu"
            )

            mem_assignment = self.expansion_heuristic_mem.generate_assignment(
                real_pods_usage,
                emulated_pods, 
                new_mapping, 
                remaining_emulated_pods,
                resource="memory"
            )

        else:
            cpu_assignment = self.apply_mapping(new_mapping, real_pods_usage, resource="cpu")
            mem_assignment = self.apply_mapping(new_mapping, real_pods_usage, resource="memory")
        
        assignment = {
            key: {
                "cpu": cpu_assignment[key],
                "memory": mem_assignment[key],
            }
            for key in cpu_assignment
        }

        workload_state["last_assignment"] = assignment

        return assignment

    def apply_mapping(self, mapping, real_pods_usage, resource, remaining_emulated_pods=None):
        resource_assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod][resource]

            resource_assignment[emulated_pod] = usage
        
        if remaining_emulated_pods:
            for emulated_pod in remaining_emulated_pods:
                resource_assignment[emulated_pod] = usage

        return resource_assignment

    def cleanup_workload(self, workload_key):
        self.state.pop(workload_key, None)