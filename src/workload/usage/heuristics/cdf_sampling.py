class CDFSamplingHeuristic:
    def generate_assignment(
        self,
        real_pods_usage,
        emulated_pods, 
        mapping,
        remaining_emulated_pods,
        resource
    ):
        
        # just a placeholder for now
        assignment = self._apply_mapping(
            mapping=mapping,
            real_pods_usage=real_pods_usage,
            resource=resource
        )

        return assignment
    

    def _apply_mapping(self, mapping, real_pods_usage, resource, remaining_emulated_pods=None):
        resource_assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod][resource]
            resource_assignment[emulated_pod] = usage
        
        if remaining_emulated_pods:
            for emulated_pod in remaining_emulated_pods:
                resource_assignment[emulated_pod] = 0

        return resource_assignment
