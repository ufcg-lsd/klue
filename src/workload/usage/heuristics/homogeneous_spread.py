import math

class HomogeneousSpreadHeuristic:
    def generate_assignment(
        self,
        real_pods_usage,
        emulated_pods_limit,
        mapping,
        remaining_real_pods,
        resource,
    ):
        """
        Compression heuristic.

        Starts by applying the stable real -> emulated pod mapping.
        Then spreads the usage of remaining real pods homogeneously
        across emulated pods, respecting emulated pod limits.

        Returns:
            {
                (namespace, emulated_pod_name): resource_usage
            }
        """
        EPS = 1e-12

        assignment = self._apply_mapping(
            mapping=mapping,
            real_pods_usage=real_pods_usage,
            resource=resource
        )

        rest = self._sum_remaining_usage(
            real_pods_usage=real_pods_usage,
            remaining_real_pods=remaining_real_pods,
            resource=resource,
        )

        if rest <= 0:
            return assignment

        headroom_list = self._get_sorted_headroom_list(assignment, emulated_pods_limit, resource)

        water_level = 0   # how much usage all pods should receive equally, taking in consideration some pods will be full
        non_full_pod_count = len(headroom_list)
        i = 0
        while i < len(headroom_list) and rest > 0:
            _, current_headroom = headroom_list[i]

            if math.isinf(current_headroom):
                # All remaining active pods have no limit, so the rest certainly fits.
                water_level += rest / non_full_pod_count
                rest = 0
                break

            true_headroom = current_headroom - water_level
            if true_headroom <= EPS:
                # considering floating point imprecision
                non_full_pod_count -= 1
                i += 1
                continue

            water_volume_possible_increment = true_headroom * non_full_pod_count 
            if water_volume_possible_increment >= rest:
                water_level += rest / non_full_pod_count
                rest = 0
                break
            else:
                rest -= water_volume_possible_increment
                water_level = current_headroom
                non_full_pod_count -= 1
                i += 1
        
        for emulated_pod, headroom in headroom_list:
            extra_usage = min(headroom, water_level)
            assignment[emulated_pod] += extra_usage

        return assignment

    def _get_sorted_headroom_list(self, assignment, emulated_pods_limit, resource):
        headroom_list = []

        for emulated_pod, current_usage in assignment.items():
            limit = emulated_pods_limit.get(emulated_pod, {}).get(resource)

            if limit is None:
                headroom = math.inf
            else:
                headroom = max(0, limit - current_usage)

            if headroom > 0 or math.isinf(headroom):
                headroom_list.append((emulated_pod, headroom))

        return sorted(headroom_list, key=lambda item: item[1])

    def _apply_mapping(self, mapping, real_pods_usage, resource, remaining_emulated_pods=None):
        resource_assignment = {}

        for real_pod, emulated_pod in mapping.items():
            usage = real_pods_usage[real_pod][resource]
            resource_assignment[emulated_pod] = usage
        
        if remaining_emulated_pods:
            for emulated_pod in remaining_emulated_pods:
                resource_assignment[emulated_pod] = 0

        return resource_assignment

    def _sum_remaining_usage(self, real_pods_usage, remaining_real_pods, resource):
        total = 0
        for real_pod in remaining_real_pods:
            total += real_pods_usage.get(real_pod, {}).get(resource, 0)

        return total
    