"""
This class processes Kubernetes pod metrics and generates yaml of these objects for emulation.
It merges multiple sources of pod-related data, and outputs structured trace and setup files.
"""

import json
import pandas as pd
from util.k8s_object_generator import K8SObjectGenerator
import os

class TracerKWOKOnly:
    """
    Processes Kubernetes pod and node metrics to generate structured trace and
    setup files suitable for KWOK emulation.

    This class ingests data from various CSV sources (pod resource requests,
    CPU usage, ownership details, status phases, replicaset ownership),
    performs several preprocessing and merging steps, and ultimately outputs
    JSON files. These files describe the initial setup (infrastructure and workload)
    and a time-series trace of events (object applications, deletions, scaling)
    for the emulation environment. It is specifically tailored to generate objects
    compatible with a KWOK-based simulation (e.g., not generating Karpenter-specific
    NodePools or Provisioners directly, as K8SObjectGenerator is called with karpenter=False).
    """

    def __init__(self, kube_pod_container_resource_requests_path, container_cpu_usage_seconds_total, sum_container_cpu_usage_seconds_total, sum_container_memory_usage_bytes, kube_pod_owner_path, kube_pod_status_phase, kube_replicaset_owner_path, instance_types_path, hpa_spec_max_replicas_path, hpa_spec_min_replicas_path, hpa_target_metric_path):
        """
        Initializes the Tracer class with the paths to various Kubernetes-related data files.
        """
        self.kube_pod_container_resource_requests_path = kube_pod_container_resource_requests_path
        self.container_cpu_usage_seconds_total_path = container_cpu_usage_seconds_total
        self.sum_container_cpu_usage_seconds_total_path = sum_container_cpu_usage_seconds_total
        self.sum_container_memory_usage_bytes_path = sum_container_memory_usage_bytes
        self.kube_pod_owner_path = kube_pod_owner_path
        self.kube_pod_status_phase_path = kube_pod_status_phase
        self.kube_replicaset_owner_path = kube_replicaset_owner_path
        self.instance_types_path = instance_types_path
        self.hpa_spec_max_replicas_path = hpa_spec_max_replicas_path
        self.hpa_spec_min_replicas_path = hpa_spec_min_replicas_path
        self.hpa_target_metric_path = hpa_target_metric_path
        self.k8s_objects_generator = K8SObjectGenerator(karpenter=False)

    def log(self, message):
        """
        Logs a message with a "[TRACER]" prefix.
        """
        print(f"[TRACER] {message}")

    def load_data(self):
        """
        Load data from CSV files into pandas DataFrames.
        Logs an informational message before loading the data.
        """
        self.log("[INFO] Loading data from CSV files.")
        self.kube_pod_container_resource_requests = pd.read_csv(self.kube_pod_container_resource_requests_path)
        self.container_cpu_usage_seconds_total = pd.read_csv(self.container_cpu_usage_seconds_total_path)
        self.sum_container_memory_usage_bytes = pd.read_csv(self.sum_container_memory_usage_bytes_path)
        self.sum_container_cpu_usage_seconds_total = pd.read_csv(self.sum_container_cpu_usage_seconds_total_path)
        self.kube_pod_owner = pd.read_csv(self.kube_pod_owner_path)
        self.kube_pod_status_phase = pd.read_csv(self.kube_pod_status_phase_path)
        self.kube_replicaset_owner = pd.read_csv(self.kube_replicaset_owner_path)
        self.hpa_spec_max_replicas = pd.read_csv(self.hpa_spec_max_replicas_path)
        self.hpa_spec_min_replicas = pd.read_csv(self.hpa_spec_min_replicas_path)
        self.hpa_target_metric = pd.read_csv(self.hpa_target_metric_path)


    def normalize_timestamps(self, dfs_list):
        """
        Normalizes the timestamps in a list of DataFrames by aligning them to a fixed range of values.

        This method adjusts the "timestamp" column in each DataFrame by subtracting the minimum timestamp
        value from all timestamps in that DataFrame. It then filters the timestamps to retain only those
        that match a predefined list of fixed intervals (0 to 14400, with a step of 300 by default).
        """
        all_timestamps = dfs_list[0]['timestamp'].unique()
        all_timestamps.sort()
        
        self.min_timestamp = all_timestamps[0]
        self.max_timestamp = all_timestamps[-1]
        self.step = all_timestamps[1] - all_timestamps[0] if len(all_timestamps) > 1 else 0

        # Get normalized informations from all metrics
        min_timestamp_normalized = 0
        max_timestamp_normalized = self.max_timestamp - self.min_timestamp
        timestamps = list(range(min_timestamp_normalized, max_timestamp_normalized + 1, self.step))

        # Normalize the timestamps of each DataFrame
        normalized_dfs = []
        for df in dfs_list:
            if "timestamp" in df.columns:
                df = df.copy()
                df["timestamp"] = df["timestamp"] - self.min_timestamp
                # Filter to keep only the timestamps that are in the fixed list
                df = df[df["timestamp"].isin(timestamps)]
            normalized_dfs.append(df)
        return normalized_dfs

    def preprocess_dataframes(self):
        """
        Preprocesses multiple dataframes by normalizing their timestamps.

        This method logs the preprocessing step and applies the `normalize_timestamps` 
        function to all dataframes in the class. It ensures that all timestamps are aligned.

        The normalized dataframes are then reassigned to their respective attributes.
        """
        self.log("[INFO] Preprocessing dataframes.")
        self.kube_pod_container_resource_requests, \
        self.container_cpu_usage_seconds_total, \
        self.sum_container_memory_usage_bytes, \
        self.sum_container_cpu_usage_seconds_total, \
        self.kube_pod_owner, \
        self.kube_pod_status_phase, \
        self.kube_replicaset_owner, \
        self.hpa_spec_max_replicas, \
        self.hpa_spec_min_replicas, \
        self.hpa_target_metric = self.normalize_timestamps([
            self.kube_pod_container_resource_requests,
            self.container_cpu_usage_seconds_total,
            self.sum_container_memory_usage_bytes,
            self.sum_container_cpu_usage_seconds_total,
            self.kube_pod_owner,
            self.kube_pod_status_phase,
            self.kube_replicaset_owner,
            self.hpa_spec_max_replicas,
            self.hpa_spec_min_replicas,
            self.hpa_target_metric
        ])

    def select_necessary_columns(self):
        """
        Selects and renames essential columns, and performs initial filtering
        on various DataFrames used in the trace generation.


        Operations performed:
        - On `self.container_cpu_usage_seconds_total`:
            - Selects 'timestamp', 'node_kubernetes_io_instance_type',
              'kubernetes_io_hostname', and 'pod'.
            - Renames 'node_kubernetes_io_instance_type' to 'instance_type'.
            - Renames 'kubernetes_io_hostname' to 'node'.
            - Removes duplicate rows based on 'pod' and 'timestamp', keeping
              the first occurrence.
        - On `self.kube_pod_container_resource_requests`:
            - Selects "timestamp", "pod", "namespace", "value", "resource",
              and "node".
        - On `self.kube_pod_owner`:
            - Removes duplicate rows based on 'pod', keeping the first occurrence.
            - Selects 'pod', 'owner_name', and 'owner_kind'.
        - On `self.kube_pod_status_phase`:
            - Filters out rows where the 'value' column (indicating phase activity) is 0.
            - Selects 'timestamp', 'pod', and 'phase'.
        - On `self.kube_replicaset_owner`:
            - Removes duplicate rows based on 'replicaset', keeping the first occurrence.
            - Selects 'replicaset', 'owner_kind', and 'owner_name'.
        - On `self.hpa_spec_max_replicas`:
            - Selects 'timestamp', 'value', 'horizontalpodautoscaler' and 'namespace".
            - Renames 'value' to 'min_replicas'.
        - On `self.hpa_spec_min_replicas`:
            - Selects 'timestamp', 'value', 'horizontalpodautoscaler' and 'namespace".
            - Renames 'value' to 'max_replicas'.
        - On `self.hpa_target_metric`:
            - Selects 'timestamp', 'value', 'metric_name', 'horizontalpodautoscaler', 'namespace', 'metric_target_type'
        """

        # Selecting only the desired final columns
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total[['timestamp', 'node_kubernetes_io_instance_type', 'kubernetes_io_hostname', 'pod']]
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total.rename(
            columns={
                'node_kubernetes_io_instance_type': 'instance_type',
                'kubernetes_io_hostname': 'node'
            }
        )
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total.drop_duplicates(subset=['pod', 'timestamp'], keep='first')

        self.kube_pod_container_resource_requests = self.kube_pod_container_resource_requests[["timestamp", "pod", "namespace", "value", "resource", "node"]]

        self.kube_pod_owner = self.kube_pod_owner.drop_duplicates(subset='pod', keep='first')
        self.kube_pod_owner = self.kube_pod_owner[['pod', 'owner_name', 'owner_kind']]

        self.kube_pod_status_phase = self.kube_pod_status_phase[self.kube_pod_status_phase['value'] != 0]
        self.kube_pod_status_phase = self.kube_pod_status_phase[['timestamp', 'pod', 'phase']]

        self.kube_replicaset_owner = self.kube_replicaset_owner.drop_duplicates(subset='replicaset', keep='first')
        self.kube_replicaset_owner = self.kube_replicaset_owner[['replicaset', 'owner_kind', 'owner_name']]

        self.hpa_spec_max_replicas = self.hpa_spec_max_replicas.loc[:, ["timestamp", "value", "__replica__", "horizontalpodautoscaler", "namespace"]].rename(columns={"value": "max_replicas"})
        self.hpa_spec_min_replicas = self.hpa_spec_min_replicas.loc[:, ["timestamp", "value", "__replica__", "horizontalpodautoscaler", "namespace"]].rename(columns={"value": "min_replicas"})
        self.hpa_target_metric = self.hpa_target_metric.loc[:, ["timestamp", "value", "__replica__", "metric_name", "horizontalpodautoscaler", "namespace", "metric_target_type"]]

    def merge_container_usage_with_pods_phase(self):
        """
        Merges container CPU usage data with pod phase data.

        This method performs a left merge of `self.container_cpu_usage_seconds_total`
        (which contains CPU usage, node, and instance type information) with
        `self.kube_pod_status_phase` (containing pod phase information) using
        'timestamp' and 'pod' as merge keys.
        Any resulting rows with missing 'phase' values are filled with 'Pending'.
        The final merged DataFrame is stored in `self.karpenter_pods_state`.
        """

        self.karpenter_pods_state = pd.merge(
            self.container_cpu_usage_seconds_total,
            self.kube_pod_status_phase,
            on=["timestamp", "pod"],
            how="left"
        ).fillna({'phase': 'Pending'})

    def merge_pods_state_with_resources(self):
        """
        Merges pod state data with resource request data, processes the
        combined data, and generates a final DataFrame with aggregated and
        pivoted resource information (CPU and memory).

        Steps:
        1. Merges `self.kube_pod_container_resource_requests` (source of resource
           requests) with `self.karpenter_pods_state` (source of pod state,
           node, instance type, and phase) using 'timestamp' and 'pod' as keys
           (left join). Suffixes are used to distinguish columns from original
           DataFrames if names clash (e.g., 'node').
        2. The 'node' column in the merged DataFrame is populated using values
           from `node_karpenter_state` (from `self.karpenter_pods_state`),
           then original suffixed node columns are dropped.
        3. Missing values in 'node', 'instance_type' are filled with "unallocated".
           Missing 'phase' values are filled with "Pending".
        4. Forward-fill and backward-fill are applied to propagate known pod
           information across timestamps where it might be missing for that pod.
        5. Duplicate rows are dropped.
        6. Resource 'value's (CPU, memory) are summed up for each unique
           combination of 'timestamp', 'pod', 'namespace', 'instance_type',
           'node', and 'resource' type.
        7. The DataFrame is pivoted to transform 'resource' types (e.g., 'cpu',
           'memory') into distinct columns.
        8. Rows where either the 'cpu' or 'memory' column still has a placeholder
           'NA' (indicating missing data for that resource type) are filtered out.
        9. The processed DataFrame is stored in `self.df_final`.
        10. Logs the count of unique pods remaining in `self.df_final`.
        """
        
        # Direct merge using 'timestamp' and 'pod' as keys
        df_merged = pd.merge(
            self.kube_pod_container_resource_requests,
            self.karpenter_pods_state,
            on=["timestamp", "pod"],
            how="left",
            suffixes=('_resource_requests', '_karpenter_state')
        ).assign(
            node=lambda df: df["node_karpenter_state"]
        ).drop(
            columns=["node_resource_requests", "node_karpenter_state"]
        )

        df_merged["node"] = df_merged["node"].fillna("unallocated")
        df_merged["instance_type"] = df_merged["instance_type"].fillna("unallocated")
        df_merged["phase"] = df_merged["phase"].fillna("Pending")

        # Filling the dataframe with the closest occurrence of this pod where there are NA values
        df_merged = df_merged.ffill().bfill()

        # Remove duplicate rows, keeping only unique ones
        df_merged = df_merged.drop_duplicates()

        df_merged.to_csv("/tmp/df_merged_before_sum.csv")

        # Sum all occurrences of CPU and memory for each timestamp of a pod
        df_merged = df_merged.groupby(['timestamp', 'pod', 'namespace', 'instance_type', 'node', 'resource']).agg({
            'value': 'sum'
        }).reset_index()

        df_merged.to_csv("/tmp/df_merged_after_sum.csv")

        # Use pivot to transform 'resource' into separate columns for 'cpu' and 'memory'
        df_pivoted = df_merged.pivot(index=['timestamp', 'pod', 'namespace', 'instance_type', 'node'],
                            columns='resource',
                            values='value').reset_index()

        # Fill missing values with 'NA' for CPU and memory
        df_pivoted['cpu'] = df_pivoted['cpu'].fillna('NA')
        df_pivoted['memory'] = df_pivoted['memory'].fillna('NA')

        self.df_final = df_pivoted[~((df_pivoted['cpu'] == 'NA') | (df_pivoted['memory'] == 'NA'))]

        # Total count of unique pods created and removed
        total_pods = self.df_final['pod'].nunique()
        self.log(f"[INFO] Number of pods after remove NAs and pods that finish on first timestamp: {total_pods}")

    def merge_pods_resources_with_pod_owner(self):
        """
        Merges the main processed DataFrame (`self.df_final`) with pod
        ownership data (`self.kube_pod_owner`).

        This is a left join on the 'pod' column, enriching `self.df_final`
        with 'owner_name' and 'owner_kind' from `self.kube_pod_owner`.
        The 'owner_name' column (typically representing a ReplicaSet name
        at this stage) is then renamed to 'replicaset' in `self.df_final`
        for clarity in subsequent steps.
        """
        self.df_final = pd.merge(self.df_final, self.kube_pod_owner, on='pod', how='left')

        self.df_final.rename(columns={'owner_name': 'replicaset'}, inplace=True)

    def merge_pods_resources_with_replicaset_owner(self):
        """
        Merges the main processed DataFrame (`self.df_final`) with ReplicaSet
        ownership data (`self.kube_replicaset_owner`).

        This method performs a left join using the 'replicaset' column.
        It then intelligently combines 'owner_kind' and 'owner_name' fields
        that might exist with suffixes (e.g., 'owner_kind_x', 'owner_kind_y')
        from the merge, prioritizing data from `kube_replicaset_owner` (`_y` suffix)
        and then from `df_final` (`_x` suffix) if the former is missing.
        The 'replicaset' column (which at this point might be the replicaset's
        owner name, like a Deployment name) is also updated using `combine_first`
        from the 'owner_name' field that comes from `kube_replicaset_owner`.
        Redundant suffixed columns are then dropped.
        The result updates `self.df_final`.
        """
        df_merged = pd.merge(self.df_final, self.kube_replicaset_owner, on='replicaset', how='left')

        df_merged['owner_kind'] = df_merged['owner_kind_y'].combine_first(df_merged['owner_kind_x'])

        df_merged['replicaset'] = df_merged['owner_name'].combine_first(df_merged['replicaset'])

        self.df_final = df_merged.drop(columns=['owner_kind_x', 'owner_kind_y'])

        self.df_final.to_csv("/tmp/df_final_after_merge_replicaset_owner.csv")

    def remove_not_considered_resources_and_namespaces(self):
        """
        Removes rows from the dataframe `df_final` that belong to namespaces or resource kinds 
        that are not considered for further processing.
        """
        self.log("[INFO] Removing not considered resources and namespaces.")
        self.df_final = self.df_final[~self.df_final['namespace'].isin(['kube-system', 'monitoring'])]

        self.df_final = self.df_final[~self.df_final['owner_kind'].isin(['DaemonSet', 'Job'])]

    """
    Converts spec_target_metrics from long to wide.
    """
    def process_hpa_target_metrics(self, spec_target_metric: pd.DataFrame) -> pd.DataFrame:
        resources = ("cpu", "memory")

        df = spec_target_metric.loc[spec_target_metric["metric_name"].isin(resources)]

        # Limits utilization metrics to the interval [0, 100]
        utilization_mask = df["metric_target_type"].astype(str).str.lower().eq("utilization")
        df.loc[utilization_mask, "value"] = pd.to_numeric(df.loc[utilization_mask, "value"], errors="coerce").clip(0, 100)

        # Converting dataframe from long to wide.
        keys = ["timestamp", "horizontalpodautoscaler", "namespace", "__replica__"]
        values = (
            df.pivot_table(
                index=keys,
                columns="metric_name",
                values="value",
                aggfunc="max",
            )
            .reindex(columns=resources)
            .reset_index()
        )

        types = (
            df.pivot_table(
                index=keys,
                columns="metric_name",
                values="metric_target_type",
                aggfunc="first",
            )
            .reindex(columns=resources)
            .reset_index()
            .rename(columns={"cpu": "cpu_type", "memory": "memory_type"})
        )

        return values.merge(types, on=keys, how="outer")


    """
    Builds a segment id for each row based on metric changes within each object.

    Rows are grouped by the object identifier`id_cols`. For each group, a new segment starts
    whenever any metric column in `metric_cols` changes compared to the previous row.
    """
    def _build_segments(self, df: pd.DataFrame, id_cols: list[str], metric_cols: list[str]) -> pd.Series:
        segment_by_index = {}

        for _, group in df.groupby(id_cols, sort=False):
            current_segment = 0
            previous_metrics = None

            for row in group.itertuples():
                current_metrics = tuple(
                    None if pd.isna(getattr(row, col)) else getattr(row, col)
                    for col in metric_cols
                )

                if previous_metrics is not None and current_metrics != previous_metrics:
                    current_segment += 1

                segment_by_index[row.Index] = current_segment
                previous_metrics = current_metrics

        return pd.Series(segment_by_index)


    """
    Builds a compact HPA metrics dataframe from multiple metric sources.

    The method merges the HPA metric inputs by timestamp, HPA name, namespace, and
    collector replica. When the same HPA/timestamp is available from multiple
    `__replica__` sources, it keeps the source that appears most often for that HPA.
    If there is a tie, the lexicographically smaller `__replica__` is selected.

    After source selection, the method compacts consecutive rows that represent the
    same HPA metric state into time ranges using `timestamp` and `last_timestamp`.
    """
    def build_hpa_metrics(
        self,
        spec_max_replicas: pd.DataFrame, 
        spec_min_replicas: pd.DataFrame, 
        spec_target_metric_wide: pd.DataFrame
    ) -> pd.DataFrame:
        join_keys = ["timestamp", "horizontalpodautoscaler", "namespace", "__replica__"]
        id_cols = ["namespace", "horizontalpodautoscaler"]
        metric_cols = ["max_replicas", "min_replicas", "cpu", "memory", "cpu_type", "memory_type"]

        hpa_metrics = (
            spec_max_replicas.merge(spec_min_replicas, on=join_keys, how="outer")
            .merge(spec_target_metric_wide, on=join_keys, how="outer")
        )

        hpa_metrics = (
            hpa_metrics
            .assign(count_metric_source=lambda x: x.groupby(["namespace", "horizontalpodautoscaler", "__replica__"])["__replica__"].transform("size"))
            .sort_values(by=["namespace", "horizontalpodautoscaler", "timestamp", "count_metric_source", "__replica__"], ascending=[True, True, True, False, True], kind="mergesort")
            .drop_duplicates(subset=["namespace", "horizontalpodautoscaler", "timestamp"], keep="first")
            .drop(columns=["count_metric_source", "__replica__"])
            .reset_index(drop=True)
        )

        hpa_metrics["_segment"] = self._build_segments(hpa_metrics, id_cols, metric_cols)

        hpa_metrics = (
            hpa_metrics
            .groupby(["namespace", "horizontalpodautoscaler", "_segment"] + metric_cols, dropna=False, as_index=False)
            .agg(timestamp=("timestamp", "min"), last_timestamp=("timestamp", "max"))
            .drop(columns=["_segment"])
            .reset_index(drop=True)
        )

        return hpa_metrics

    def build_hpa_trace(self):
        self.log("[INFO] Building optional HPA trace.")

        spec_target_metric_wide = self.process_hpa_target_metrics(self.hpa_target_metric)
        hpa_metrics = self.build_hpa_metrics(
            self.hpa_spec_max_replicas,
            self.hpa_spec_min_replicas,
            spec_target_metric_wide,
        )

        if hpa_metrics.empty:
            self.df_hpa_trace = pd.DataFrame(columns=[
                "timestamp",
                "horizontalpodautoscaler",
                "namespace",
                "max_replicas",
                "min_replicas",
                "cpu",
                "memory",
                "cpu_type",
                "memory_type",
                "action",
            ])
            return

        hpa_metrics = hpa_metrics.sort_values(["namespace", "horizontalpodautoscaler", "timestamp"]).reset_index(drop=True)

        hpa_metrics.to_csv("/tmp/hpa_metrics.csv")

        apply_action = hpa_metrics.copy()
        apply_action["action"] = "apply"

        delete_rows = hpa_metrics.groupby(["namespace", "horizontalpodautoscaler"], as_index=False).tail(1).copy()
        delete_rows["timestamp"] = min(delete_rows["last_timestamp"].astype(int) + self.step, self.max_timestamp)
        delete_rows["action"] = "delete"

        self.df_hpa_trace = pd.concat([apply_action, delete_rows], ignore_index=True, sort=False)
        self.df_hpa_trace = self.df_hpa_trace.sort_values(["timestamp", "namespace", "horizontalpodautoscaler", "action"]).reset_index(drop=True)
        self.df_hpa_trace.to_csv("/tmp/hpa.csv")

    def process_and_save_pods_allocation(self):
        """
        Processes and saves pod allocation data.

        This method filters and processes pod allocation data from the `df_final` DataFrame,
        saving the results into two CSV files:
        1. A list of all unique nodes involved in the allocation.
        2. A detailed summary of pod allocations grouped by namespace, node, replicaset,
           owner kind, and instance type.

        Additionally, removes nodes that appear in only one timestamp.
        """
        self.log("[INFO] Processing and saving pods allocation.")
        df_pods_allocation = self.df_final[self.df_final['timestamp'] == self.df_final['timestamp'].min()]

        df_pods_allocation.to_csv("/tmp/df_pods_allocation_not_final.csv")

        df_pods_allocation = df_pods_allocation[~df_pods_allocation["node"].isin(["unallocated"]) & ~df_pods_allocation["instance_type"].isin(["unallocated"])]

        # Remove nodes that appear in only one timestamp in the whole trace
        node_timestamp_counts = self.df_final.groupby('node')['timestamp'].nunique()
        valid_nodes = node_timestamp_counts[node_timestamp_counts > 1].index
        df_pods_allocation = df_pods_allocation[df_pods_allocation['node'].isin(valid_nodes)]

        self.df_pods_allocation_test = df_pods_allocation.groupby(
            ['namespace', 'node', 'replicaset', 'owner_kind', 'instance_type']
        ).agg(
            pods_count=('replicaset', 'count'),
            pods=('pod', lambda x: list(x))
        ).reset_index()
        
        self.df_pods_allocation = df_pods_allocation.groupby(['namespace', 'node', 'replicaset', 'owner_kind', 'instance_type']).agg(
            pods_count=('replicaset', 'count'),
        ).reset_index()

        self.df_pods_allocation.to_csv("/tmp/pods_allocation.csv", index=False)

    def process_and_save_final_trace(self):
        """
        Processes and saves the final trace data by aggregating and transforming the dataframe.
        The resulting CSV file contains the final trace data with the following columns:
        - 'timestamp', 'namespace', 'replicaset', 'owner_kind', 'pods', 'cpu', 'memory', and 'action'.
        """
        self.log("[INFO] Processing and saving final trace.")
        df_adjusted = self.df_final.groupby(['timestamp', 'namespace', 'replicaset', 'owner_kind']).agg(
            pods_count=('replicaset', 'count'),
            cpu_count=('cpu', 'mean'),
            memory_count=('memory', 'mean')
        ).reset_index()

        df_adjusted = df_adjusted.rename(columns={'pods_count': 'pods', 'cpu_count': 'cpu', 'memory_count': 'memory'})

        # This step is to add the action related to the replicaset
        df_adjusted['action'] = 'scale'

        first_occurrences = df_adjusted.groupby(['replicaset','namespace']).head(1).index
        df_adjusted.loc[first_occurrences, 'action'] = 'create'

        last_occurrences = df_adjusted.groupby(['replicaset','namespace']).tail(1).index
        df_adjusted.loc[last_occurrences, 'action'] = 'delete'

        df_adjusted['pods_changed'] = df_adjusted.groupby('replicaset')['pods'].diff().fillna(1) != 0

        self.df_final = df_adjusted[df_adjusted['pods_changed'] | (df_adjusted['action'].isin(['create', 'delete']))].drop(columns=['pods_changed'])

    def merge_applied_objects(self, *objects_maps):
        merged = {}

        for objects_map in objects_maps:
            for namespace, objects in objects_map.items():
                merged.setdefault(namespace, [])
                merged[namespace].extend(objects)

        return merged

    def generate_workload_objects(self):
        """
        Generates structured workload objects for setup and emulation phases.

        This method iterates through `self.df_final` grouped by 'timestamp'.
        - For the very first timestamp, it generates initial deployment objects
          which are considered as 'setup' data.
        - For all subsequent timestamps, it generates applied objects (new
          deployments), deleted objects (names of deployments to remove), and
          scaled replicasets based on the trace data for that timestamp.
          These are added to the 'emulation' list.

        It utilizes `self.k8s_objects_generator.generate_deployments()` to
        create the Kubernetes object representations.

        Returns:
            dict: A dictionary structured for emulation, containing:
                - 'setup' (dict): Deployment objects for the initial setup phase,
                  as returned by the K8SObjectGenerator for the first timestamp.
                - 'emulation' (list): A list of dictionaries, each representing
                  a time-stepped entry in the emulation trace. Each entry includes:
                    - "timestamp" (int): The normalized timestamp of the event.
                    - "applied_objects" (list): Kubernetes objects (e.g., Deployments)
                      to be applied at this timestamp.
                    - "deleted_objects" (list): Names of objects to be deleted.
                    - "scaled_replicasets" (list): Information about replicasets
                      that need scaling.
        """
        workload_objects = {
            'setup': {
                'applied_objects': {},
                'workload_actions': []
            },
            'emulation': []
        }


        # =========================
        # UNION DOS TIMESTAMPS
        # =========================
        timestamps = sorted(
            set(self.df_final['timestamp']) |
            set(self.df_container_usage['timestamp']) |
            set(self.df_hpa_trace['timestamp'])
        )

        first_timestamp = min(timestamps)

        for timestamp in timestamps:
            timestamp = int(timestamp)

            # =========================
            # FILTRA DADOS
            # =========================
            group_final = self.df_final[self.df_final['timestamp'] == timestamp]
            group_usage = self.df_container_usage[self.df_container_usage['timestamp'] == timestamp]
            group_usage = group_usage.groupby(['namespace', 'replicaset']).agg(
                            cpu_usage=('cpu_usage', 'sum'),
                            memory_usage=('memory_usage', 'sum')
                        ).reset_index()
            group_hpa = self.df_hpa_trace[self.df_hpa_trace['timestamp'] == timestamp]


            # =========================
            # DEPLOYMENT EVENTS (scale/create/delete)
            # =========================
            applied_objects = {}
            deleted_objects = []
            workload_actions_scale = []

            if not group_final.empty:
                applied_objects, deleted_objects, workload_actions_scale = \
                    self.k8s_objects_generator.generate_deployments(group_final)


            # =========================
            # HPA EVENTS (scale/create/delete)
            # =========================     
            applied_hpa_objects = {}
            deleted_hpa_objects = []

            if not group_hpa.empty:
                applied_hpa_objects, deleted_hpa_objects = self.k8s_objects_generator.generate_hpa(group_hpa)

            # =========================
            # MERGING EVENTS (scale/create/delete)
            # =========================    
            applied_objects = self.merge_applied_objects(applied_objects, applied_hpa_objects)
            deleted_objects = deleted_objects + deleted_hpa_objects

            # =========================
            # USAGE EVENTS (set-usage)
            # =========================
            workload_actions_usage = []

            if not group_usage.empty:
                workload_actions_usage = \
                    self.k8s_objects_generator.generate_usage_workload_action(group_usage)

            # =========================
            # MERGE DOS WORKLOAD ACTIONS
            # =========================
            workload_actions = workload_actions_scale + workload_actions_usage

            # =========================
            # BUILD FINAL STRUCTURE
            # =========================
            if timestamp == first_timestamp:
                workload_objects['setup']['applied_objects'] = applied_objects
                workload_objects['setup']['workload_actions'] = workload_actions
            else:
                workload_objects['emulation'].append({
                    "timestamp": timestamp,
                    "applied_objects": applied_objects,
                    "deleted_objects": deleted_objects,
                    "workload_actions": workload_actions
                })

        return workload_objects
    
    def process_and_save_infrastructure_objects(self):
        """
        Processes `self.df_final` to identify and mark node creation and
        deletion events based on their first and last appearance with a specific
        instance type. The result is stored in `self.df_infrastructure`.

        Steps:
        1. Copies `self.df_final` to `self.df_infrastructure`.
        2. Selects unique combinations of 'timestamp', 'node', and 'instance_type'.
        3. Sorts by 'node', 'instance_type', and 'timestamp'.
        4. For each ('node', 'instance_type') pair, marks the first timestamped
           occurrence as a 'create' action and the last as a 'delete' action.
        5. Filters to keep only these 'create' and 'delete' action rows.
        6. Further filters to retain only ('node', 'instance_type') pairs that
           have more than one action (i.e., both a create and a delete, implying
           the node existed for some duration).
        7. Removes entries where 'node' or 'instance_type' is "unallocated".
        8. The final DataFrame, sorted by timestamp, action, instance_type,
           and node, is stored in `self.df_infrastructure`.
        An informational message is logged before processing.
        """
        self.log("[INFO] Processing and saving infrastructure objects.")

        # Saving the final_trace to obtain the infrastructure objects
        self.df_infrastructure = self.df_final.copy()

        # Marcar a primeira e a última ocorrência de cada nó (com instance_type), independente do timestamp
        infra = self.df_infrastructure[['timestamp', 'node', 'instance_type']].drop_duplicates()

        # Para cada node/instance_type, marcar a primeira e última ocorrência
        infra = infra.sort_values(['node', 'instance_type', 'timestamp'])
        first_idx = infra.groupby(['node', 'instance_type']).head(1).index
        last_idx = infra.groupby(['node', 'instance_type']).tail(1).index

        infra['action'] = ''
        infra.loc[first_idx, 'action'] = 'create'
        infra.loc[last_idx, 'action'] = 'delete'

        # Manter apenas os eventos 'create' e 'delete'
        infra = infra[infra['action'].isin(['create', 'delete'])]

        # Remover nodes com valores faltantes ou que só aparecem uma vez
        counts = infra.groupby(['node', 'instance_type'])['action'].count()
        valid_nodes = counts[counts > 1].index
        infra = infra.set_index(['node', 'instance_type']).loc[valid_nodes].reset_index()

        infra = infra[(infra['node'] != 'unallocated') & (infra['instance_type'] != 'unallocated')]

        self.df_infrastructure = infra.sort_values(['timestamp', 'action', 'instance_type', 'node'])

    def generate_infrastructure_objects(self):
        """
        Generates structured data for infrastructure (Node) object lifecycle events.

        This method processes `self.df_infrastructure`, which contains 'create'
        and 'delete' actions for nodes at specific timestamps. It loads instance
        type definitions from `self.instance_types_path` to generate full
        Kubernetes Node object specifications using `self.k8s_objects_generator.generate_node()`.

        The output dictionary separates initial node setup from subsequent
        emulation events (node additions/removals).

        Returns:
            dict: A dictionary with two keys:
                - 'setup' (list): A list of full Node objects that are marked
                  for creation at the very first timestamp in `self.df_infrastructure`.
                - 'emulation' (list): A list of dictionaries, one for each
                  timestamp present in `self.df_infrastructure`. Each dictionary includes:
                    - "timestamp" (int): The normalized timestamp of the event.
                    - "applied_objects" (list): Full Node objects to be created at
                      this timestamp (this list is empty if the current timestamp
                      is the first one, as those nodes go into the 'setup' list).
                    - "deleted_objects" (list): Names (strings) of Node objects
                      to be deleted at this timestamp.
        """
        first_timestamp = self.df_infrastructure['timestamp'].min()

        infrastructure_objects = {'setup': [], 'emulation': []}

        with open(self.instance_types_path, encoding="utf-8") as f:
            instance_data = json.load(f)

        for timestamp, group in self.df_infrastructure.groupby('timestamp'):
            # Each 'group' is a DataFrame containing rows for the current timestamp,
            # with columns: ['timestamp', 'node', 'instance_type', 'action']
            applied_objects = []
            deleted_objects = []
            for _, row in group.iterrows():
                instance_name = row['node']
                instance_type = row['instance_type']
                action = row['action']

                if action == 'delete':
                    deleted_objects.append(instance_name)
                else:
                    node = self.k8s_objects_generator.generate_node(instance_type, instance_data, instance_name)
                    target_list = infrastructure_objects['setup'] if timestamp == first_timestamp else applied_objects
                    target_list.append(node)

            infrastructure_objects['emulation'].append({
                "timestamp": int(timestamp),
                "applied_objects": applied_objects,
                "deleted_objects": deleted_objects
            })


        return infrastructure_objects

    def process_and_save_workload_and_infrastructure_objects(self):
        """
        Processes and saves the output objects generated by the trace emulation.
        """
        self.log("[INFO] Processing and saving output objects.")
        workload_objects = self.generate_workload_objects()
        infrastructure_objects = self.generate_infrastructure_objects()

        workload_objects_json = json.dumps(workload_objects, indent=4)
        infrastructure_objects_json = json.dumps(infrastructure_objects, indent=4)

        with open('/tmp/workload_description.json', 'w', encoding="utf-8") as f:
            f.write(workload_objects_json)

        with open('/tmp/infrastructure_description.json', 'w', encoding="utf-8") as f:
            f.write(infrastructure_objects_json)
    
    def build_container_usage_df(self):
        """
        Builds container-level usage dataframe (cpu + memory).
        """

        self.log("[INFO] Building container-level usage dataframe.")

        # =========================
        # RENAME BEFORE MERGE
        # =========================
        cpu_df = self.sum_container_cpu_usage_seconds_total.rename(
            columns={'value': 'cpu_usage'}
        )

        mem_df = self.sum_container_memory_usage_bytes.rename(
            columns={'value': 'memory_usage'}
        )


        # =========================
        # MERGE CPU + MEMORY
        # =========================
        usage_df = pd.merge(
            cpu_df[['timestamp', 'pod', 'namespace', 'cpu_usage']],
            mem_df[['timestamp', 'pod', 'namespace', 'memory_usage']],
            on=['timestamp', 'pod', 'namespace'],
            how='outer'
        )

        # preencher gaps após merge
        usage_df = usage_df.sort_values(['pod', 'timestamp'])

        usage_df.to_csv("/tmp/derikiiii.csv", index=False)

        # =========================
        # ADD REPLICASET
        # =========================
        usage_df = pd.merge(
            usage_df,
            self.kube_pod_owner[['pod', 'owner_name']],
            on='pod',
            how='left'
        ).rename(columns={'owner_name': 'replicaset'})

        # =========================
        # ADD DEPLOYMENT (REPLICASET OWNER)
        # =========================
        usage_df = pd.merge(
            usage_df,
            self.kube_replicaset_owner[['replicaset', 'owner_name']],
            on='replicaset',
            how='left'
        )

        # substituir replicaset pelo deployment (owner)
        usage_df['replicaset'] = usage_df['owner_name'].combine_first(usage_df['replicaset'])

        # remover coluna auxiliar
        usage_df = usage_df.drop(columns=['owner_name'])

        # =========================
        # AGGREGATE BY REPLICASET
        # =========================
        usage_df = usage_df.groupby(
            ['timestamp', 'namespace', 'replicaset']
        ).agg(
            cpu_usage=('cpu_usage', 'sum'),
            memory_usage=('memory_usage', 'sum')
        ).reset_index()

        usage_df = usage_df [usage_df['replicaset'].isin(self.df_final['replicaset'])]

        # =========================
        # CONVERT MEMORY TO Gi
        # =========================
        usage_df['memory_usage'] = usage_df['memory_usage'] / (1024 ** 3)

        # =========================
        # FINAL
        # =========================
        self.df_container_usage = usage_df

        self.df_container_usage.to_csv("/tmp/df_container_usage.csv", index=False)

        self.log("[INFO] Container usage dataframe built.")

    def run(self):
        """
        Executes the main workflow of the Tracer class.

        This method orchestrates the entire tracing process by calling the appropriate
        helper methods in the correct sequence.
        """
        self.log("[INFO] Starting Tracer.")
        self.load_data()
        self.preprocess_dataframes()
        self.select_necessary_columns()
        self.merge_container_usage_with_pods_phase()
        self.merge_pods_state_with_resources()
        self.merge_pods_resources_with_pod_owner()
        self.merge_pods_resources_with_replicaset_owner()
        self.build_container_usage_df()
        self.remove_not_considered_resources_and_namespaces()
        self.build_hpa_trace()
        self.process_and_save_pods_allocation()
        self.process_and_save_infrastructure_objects()
        self.process_and_save_final_trace()
        self.process_and_save_workload_and_infrastructure_objects()