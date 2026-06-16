from workload.usage.heuristics.homogeneous_spread import HomogeneousSpreadHeuristic
from workload.usage.heuristics.inverse_cdf_sampling import InverseCDFSamplingHeuristic

class UsageAssignmentEngine:
    """
    Engine responsible for assigning real pod usage to emulated pods.
    The UsageManager is responsible for discovering Kubernetes pods and applying
    the resulting usage. This engine only decides the assignment.

    This module keeps a stable mapping between real pods and emulated pods for
    each workload, as well as the last decided assignment.

    On every reconciliation, the engine:
    - removes stale mappings;
    - maps newly observed real pods to available emulated pods;
    - detects whether there are more real pods or more emulated pods;
    - delegates compression/expansion behavior to the configured heuristics;
    """


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


        # Heuristics are configured separately per resource.
        # This allows CPU and memory to use different strategies in the future,
        # even though both currently use the same compression and expansion heuristic.
        self.compression_heuristic_cpu = HomogeneousSpreadHeuristic()
        self.compression_heuristic_mem = HomogeneousSpreadHeuristic()
        self.expansion_heuristic_cpu = InverseCDFSamplingHeuristic()
        self.expansion_heuristic_mem = InverseCDFSamplingHeuristic()

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
                real_pods_usage=real_pods_usage,
                emulated_pods_limit=emulated_pods_limit,
                mapping=new_mapping,
                remaining_real_pods=remaining_real_pods,
                resource="cpu",
            )

            mem_assignment = self.compression_heuristic_mem.generate_assignment(
                real_pods_usage=real_pods_usage,
                emulated_pods_limit=emulated_pods_limit,
                mapping=new_mapping,
                remaining_real_pods=remaining_real_pods,
                resource="memory",
            )

        elif remaining_emulated_pods:
            cpu_assignment = self.expansion_heuristic_cpu.generate_assignment(
                real_pods_usage=real_pods_usage,
                emulated_pods=emulated_pods,
                mapping=new_mapping,
                remaining_emulated_pods=remaining_emulated_pods,
                resource="cpu",
            )

            mem_assignment = self.expansion_heuristic_mem.generate_assignment(
                real_pods_usage=real_pods_usage,
                emulated_pods=emulated_pods,
                mapping=new_mapping,
                remaining_emulated_pods=remaining_emulated_pods,
                resource="memory",
            )

        else:
            cpu_assignment = self.apply_mapping(new_mapping, real_pods_usage, resource="cpu")
            mem_assignment = self.apply_mapping(new_mapping, real_pods_usage, resource="memory")
        
        # merge resource-specific assignments into the final pod assignment.
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
        """
        Build the initial assignment from the stable real -> emulated pod mapping.

        Mapped emulated pods initially receive the exact usage of their mapped
        real pod.

        Remaining emulated pods initially receive 0.
        """
        resource_assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod][resource]
            resource_assignment[emulated_pod] = usage
        
        if remaining_emulated_pods:
            for emulated_pod in remaining_emulated_pods:
                resource_assignment[emulated_pod] = 0

        return resource_assignment

    def cleanup_workload(self, workload_key):
        """
        Remove all engine state for a workload.

        This should be called when the workload disappears from the emulation,
        for example when its Deployment is deleted.
        """
        self.state.pop(workload_key, None)