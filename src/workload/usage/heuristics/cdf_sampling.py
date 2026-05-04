class CDFSamplingHeuristic:
    def generate_assignment(
        self,
        real_pods_usage,
        real_pods_limit, 
        emulated_pods, 
        mapping,
        previous_assignment,
        remaining_pods,
        resource
    ):
        return