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

    def resolve(self, workload_key, real_pods_usage, real_pods_limit, emulated_pods):
        """
        Args:
            workload_key:
                (namespace, workload_name)

            real_pods_usage and real_pods_limit:
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
        
        # calling scaling down / scaling up / no-scale heuristics accordingly
        remaining_real_pods = unmapped_real_pods[n:]
        remaining_emulated_pods = unmapped_emulated_pods[n:]

        if remaining_real_pods:
            # assignment = self._generate_resource_assignment(
            #     cpu_heuristic=self.compression_heuristic_cpu,
            #     mem_heuristic=self.compression_heuristic_mem,
            #     real_pods_usage=real_pods_usage,
            #     real_pods_limit=real_pods_limit, 
            #     emulated_pods=emulated_pods, 
            #     mapping=new_mapping,
            #     previous_assignment=workload_state["last_assignment"],
            #     remaining_pods=remaining_real_pods
            # )
            assignment = self._apply_mapping(new_mapping, real_pods_usage)

        elif remaining_emulated_pods:
            # assignment = self._generate_resource_assignment(
            #     cpu_heuristic=self.expansion_heuristic_cpu,
            #     mem_heuristic=self.expansion_heuristic_mem,
            #     real_pods_usage=real_pods_usage,
            #     real_pods_limit=real_pods_limit, 
            #     emulated_pods=emulated_pods, 
            #     mapping=new_mapping, 
            #     previous_assignment=workload_state["last_assignment"],
            #     remaining_pods=remaining_emulated_pods
            # )
            assignment = self._apply_mapping(new_mapping, real_pods_usage)

        else:
            assignment = self._apply_mapping(new_mapping, real_pods_usage)
            
        workload_state["last_assignment"] = assignment

        return assignment
    
    def _generate_resource_assignment(
            self, 
            cpu_heuristic, 
            mem_heuristic,
            real_pods_usage,
            real_pods_limit,
            emulated_pods, 
            mapping,
            previous_assignment,
            remaining_pods
        ):

        assignment_cpu = cpu_heuristic.generate_assignment(
            real_pods_usage,
            real_pods_limit, 
            emulated_pods, 
            mapping,
            previous_assignment,
            remaining_pods,
            resource="cpu"
        )

        assignment_mem = mem_heuristic.generate_assignment(
            real_pods_usage,
            real_pods_limit, 
            emulated_pods, 
            mapping, 
            previous_assignment,
            remaining_pods,
            resource="memory"
        )

        if assignment_cpu.keys() != assignment_mem.keys():
            raise ValueError("CPU and memory assignments target different pod sets")

        return {
            key: {
                "cpu": assignment_cpu[key],
                "memory": assignment_mem[key],
            }
            for key in assignment_cpu
        }

    def _apply_mapping(self, mapping, real_pods_usage, remaining_emulated_pods=None):
        assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod]

            assignment[emulated_pod] = {
                "cpu": usage["cpu"],
                "memory": usage["memory"],
            }
        
        if remaining_emulated_pods:
            for emulated_pod in remaining_emulated_pods:
                assignment[emulated_pod] = {
                    "cpu": 0,
                    "memory": 0,
                }

        return assignment

    def cleanup_workload(self, workload_key):
        self.state.pop(workload_key, None)