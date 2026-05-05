import math

class InverseCDFSamplingHeuristic:
    def generate_assignment(
        self,
        real_pods_usage,
        emulated_pods, 
        mapping,
        remaining_emulated_pods,
        resource
    ):
        """
        Expansion heuristic.

        Generates a resource assignment using inverse-CDF sampling.

        Strategy:
        - Build a sampled distribution with one value per emulated pod.
        - Normalize sampled values so total emulated usage == total real usage.
        - For already mapped pods, assign the sampled value closest to the real pod usage.
        - For remaining emulated pods, assign the remaining sampled values deterministically by sorted pod name.

        Returns:
            {
                (namespace, emulated_pod_name): resource_usage
            }
        """
        # initial assignment
        assignment = self._apply_mapping(
            mapping=mapping,
            real_pods_usage=real_pods_usage,
            resource=resource,
            remaining_emulated_pods=remaining_emulated_pods
        )

        if not remaining_emulated_pods or not real_pods_usage:
            return assignment
        
        resources = [usage[resource] for usage in real_pods_usage.values()]
        representative_p = self._representative_percentiles(len(emulated_pods))
        sampled_resources = [self._inv_cdf(resources, p) for p in representative_p]
        normalized_resources = self._normalize_resources(resources, sampled_resources)

        # Assign normalized sampled values to mapped emulated pods,
        # choosing the sampled value closest to each corresponding real pod usage.
        for real_pod, emulated_pod in sorted(mapping.items()):
            real_usage = real_pods_usage[real_pod][resource]

            closest_index = self._find_closest_index(
                values=normalized_resources,
                target=real_usage
            )

            assignment[emulated_pod] = normalized_resources.pop(closest_index)

        # Assign leftover sampled values to remaining emulated pods deterministically.
        for emulated_pod, sampled_usage in zip(sorted(remaining_emulated_pods), sorted(normalized_resources)):
            assignment[emulated_pod] = sampled_usage

        return assignment

    def _representative_percentiles(self, n):
        """
        Return n deterministic representative percentiles in the middle
        of each equal-width n intervals of [0, 1].

        Example:
            n = 4

            Intervals:
                [0.00, 0.25]
                [0.25, 0.50]
                [0.50, 0.75]
                [0.75, 1.00]

            Returned midpoints: [0.125, 0.375, 0.625, 0.875]

        These percentiles are used so that the heuristic is deterministic and reproducible.
        """
        interval_length = 1 / n
        intervals_start = [interval_length * i for i in range(n)]
        intervals_mid_point = [s + interval_length/2 for s in intervals_start]
        return intervals_mid_point

    def _inv_cdf(self, values, p):
        """
        Evaluate the inverse CDF at p.

        The input values are sorted, and p is converted into a
        position over the sorted list. If the position falls between two
        observed values, linear interpolation is used.

        Example:
            values = [10, 20, 30]
            p = 0.25

            position = 0.25 * (3 - 1) = 0.5

            Result: halfway between 10 and 20 = 15
        """
        values = sorted(values)

        position = p * (len(values) - 1)
        
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        # if the position is exact, no interpolation is needed
        if lower_index == upper_index:
            return values[lower_index]

        lower_value = values[lower_index]
        upper_value = values[upper_index]

        # linear interpolation
        weight = position - lower_index
        return lower_value + weight * (upper_value - lower_value)

    def _normalize_resources(self, actual_resources, sampled_resources):
        """
        Scale sampled resource values so their total equals the total real usage.

        This preserves the total workload usage after expansion.
        """
        S1 = sum(actual_resources)
        S2 = sum(sampled_resources)

        if S2 == 0: 
            # Should not happen under normal circunstances. 
            # When it does happen, the total real resource usage is also expected to be 0, which would make 'equal_value' also equal to 0.
            equal_value = S1 / len(sampled_resources)
            return [equal_value] * len(sampled_resources)

        return [n * S1/S2 for n in sampled_resources]

    def _find_closest_index(self, values, target):
        """
        Return the index of the value closest to target.
        """
        closest_index = 0
        closest_distance = abs(values[0] - target)

        for index, value in enumerate(values[1:], start=1):
            distance = abs(value - target)

            if distance < closest_distance:
                closest_index = index
                closest_distance = distance

        return closest_index

    def _apply_mapping(self, mapping, real_pods_usage, resource, remaining_emulated_pods=None):
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

