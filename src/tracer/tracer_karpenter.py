"""
This class processes Kubernetes pod metrics and generates yaml of these objects for emulation.
It merges multiple sources of pod-related data, and outputs structured trace and setup files.
"""

import json
import pandas as pd
from util.k8s_object_generator import K8SObjectGenerator

class TracerKarpenter:
    """
    The Tracer class is responsible for processing Kubernetes pod and node data to generate
    a trace of resource allocation and usage over time. It integrates data from multiple
    sources, normalizes timestamps, preprocesses dataframes, and generates output files
    and objects for further analysis.

    Parameters:
        kube_pod_container_resource_requests_path (str): Path to the CSV file containing pod container resource requests.
        kube_pod_container_resource_limits_path (str): Path to the CSV file containing pod container resource limits.
        container_cpu_usage_seconds_total_path (str): Path to the CSV file containing container CPU usage counter.
        container_memory_usage_bytes_path (str): Path to the CSV file containing container memory usage.
        karpenter_pods_state_path (str): Path to the CSV file containing Karpenter pod state information.
        kube_pod_owner_path (str): Path to the CSV file containing pod owner information.
        kube_replicaset_owner_path (str): Path to the CSV file containing replicaset owner information.
        instance_types_path (str): Path to the JSON file containing instance type definitions.
        hpa_spec_max_replicas_path (str): Path to the CSV file containing HPA max replicas specifications.
        hpa_spec_min_replicas_path (str): Path to the CSV file containing HPA min replicas specifications.
        hpa_target_metric_path (str): Path to the CSV file containing HPA target metrics.
    """

    def __init__(
        self,
        kube_pod_container_resource_requests_path,
        kube_pod_container_resource_limits_path,
        container_cpu_usage_seconds_total_path,
        container_memory_usage_bytes_path,
        karpenter_pods_state_path,
        kube_pod_owner_path,
        kube_replicaset_owner_path,
        instance_types_path,
        hpa_spec_max_replicas_path,
        hpa_spec_min_replicas_path,
        hpa_target_metric_path,
    ):
        self.kube_pod_container_resource_requests_path = kube_pod_container_resource_requests_path
        self.kube_pod_container_resource_limits_path = kube_pod_container_resource_limits_path
        self.container_cpu_usage_seconds_total_path = container_cpu_usage_seconds_total_path
        self.container_memory_usage_bytes_path = container_memory_usage_bytes_path
        self.karpenter_pods_state_path = karpenter_pods_state_path
        self.kube_pod_owner_path = kube_pod_owner_path
        self.kube_replicaset_owner_path = kube_replicaset_owner_path
        self.instance_types_path = instance_types_path
        self.hpa_spec_max_replicas_path = hpa_spec_max_replicas_path
        self.hpa_spec_min_replicas_path = hpa_spec_min_replicas_path
        self.hpa_target_metric_path = hpa_target_metric_path
        self.k8s_objects_generator = K8SObjectGenerator()

    def log(self, message):
        print(f"[TRACER] {message}")

    def load_data(self):
        self.log("[INFO] Loading data from CSV files.")
        self.kube_pod_container_resource_requests = pd.read_csv(self.kube_pod_container_resource_requests_path)
        self.kube_pod_container_resource_limits = pd.read_csv(self.kube_pod_container_resource_limits_path)
        self.container_cpu_usage_seconds_total = pd.read_csv(self.container_cpu_usage_seconds_total_path)
        self.container_memory_usage_bytes = pd.read_csv(self.container_memory_usage_bytes_path)
        self.karpenter_pods_state = pd.read_csv(self.karpenter_pods_state_path)
        self.kube_pod_owner = pd.read_csv(self.kube_pod_owner_path)
        self.kube_replicaset_owner = pd.read_csv(self.kube_replicaset_owner_path)
        self.hpa_spec_max_replicas = pd.read_csv(self.hpa_spec_max_replicas_path)
        self.hpa_spec_min_replicas = pd.read_csv(self.hpa_spec_min_replicas_path)
        self.hpa_target_metric = pd.read_csv(self.hpa_target_metric_path)

    def normalize_timestamps(self, dfs_list):
        """
        Normalizes the timestamps in a list of DataFrames by aligning them to a fixed range of values.
        """
        all_timestamps = dfs_list[0]['timestamp'].unique()
        all_timestamps.sort()

        self.min_timestamp = all_timestamps[0]
        self.max_timestamp = all_timestamps[-1]
        self.step = all_timestamps[1] - all_timestamps[0] if len(all_timestamps) > 1 else 0

        min_timestamp_normalized = 0
        max_timestamp_normalized = self.max_timestamp - self.min_timestamp
        timestamps = list(range(min_timestamp_normalized, max_timestamp_normalized + 1, self.step))

        normalized_dfs = []
        for df in dfs_list:
            if "timestamp" in df.columns:
                df = df.copy()
                df["timestamp"] = df["timestamp"] - self.min_timestamp
                df = df[df["timestamp"].isin(timestamps)]
            normalized_dfs.append(df)
        return normalized_dfs

    def preprocess_dataframes(self):
        self.log("[INFO] Preprocessing dataframes.")
        (
            self.kube_pod_container_resource_requests,
            self.kube_pod_container_resource_limits,
            self.container_cpu_usage_seconds_total,
            self.container_memory_usage_bytes,
            self.karpenter_pods_state,
            self.kube_pod_owner,
            self.kube_replicaset_owner,
            self.hpa_spec_max_replicas,
            self.hpa_spec_min_replicas,
            self.hpa_target_metric,
        ) = self.normalize_timestamps([
            self.kube_pod_container_resource_requests,
            self.kube_pod_container_resource_limits,
            self.container_cpu_usage_seconds_total,
            self.container_memory_usage_bytes,
            self.karpenter_pods_state,
            self.kube_pod_owner,
            self.kube_replicaset_owner,
            self.hpa_spec_max_replicas,
            self.hpa_spec_min_replicas,
            self.hpa_target_metric,
        ])

    def select_necessary_columns(self):
        if "pod" not in self.karpenter_pods_state.columns:
            self.karpenter_pods_state["pod"] = self.karpenter_pods_state["name...4"]

        self.karpenter_pods_state = self.karpenter_pods_state[['timestamp', 'instance_type', 'node', 'pod', 'nodepool', 'phase']]

        self.kube_pod_container_resource_requests = self.kube_pod_container_resource_requests[["timestamp", "pod", "namespace", "value", "resource", "node"]]
        self.kube_pod_container_resource_limits = self.kube_pod_container_resource_limits[["timestamp", "pod", "namespace", "value", "resource", "node"]]

        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total[['timestamp', 'namespace', 'pod', 'container', 'value']]
        self.container_memory_usage_bytes = self.container_memory_usage_bytes[['timestamp', 'namespace', 'pod', 'container', 'value']]

        self.kube_pod_owner = (
            self.kube_pod_owner[["namespace", "pod", "owner_name", "owner_kind"]]
            .drop_duplicates()
        )

        self.kube_replicaset_owner = (
            self.kube_replicaset_owner[['namespace', 'replicaset', 'owner_kind', 'owner_name']]
            .drop_duplicates()
        )

        self.hpa_spec_max_replicas = self.hpa_spec_max_replicas[["timestamp", "value", "horizontalpodautoscaler", "namespace"]].rename(columns={"value": "max_replicas"})
        self.hpa_spec_min_replicas = self.hpa_spec_min_replicas[["timestamp", "value", "horizontalpodautoscaler", "namespace"]].rename(columns={"value": "min_replicas"})
        self.hpa_target_metric = self.hpa_target_metric[["timestamp", "value", "metric_name", "horizontalpodautoscaler", "namespace", "metric_target_type"]]

    def merge_pods_state_with_resources(self):
        """
        Merges pod state (from karpenter_pods_state) with resource requests and limits,
        producing cpu_request, memory_request, cpu_limit, memory_limit columns.
        """
        df_merged = pd.merge(
            pd.concat(
                [
                    self.kube_pod_container_resource_requests.assign(resource_kind="request"),
                    self.kube_pod_container_resource_limits.assign(resource_kind="limit"),
                ],
                ignore_index=True
            ),
            self.karpenter_pods_state,
            on=["timestamp", "pod"],
            how="left",
            suffixes=("_resource", "_karpenter_state")
        ).assign(
            node=lambda df: df["node_karpenter_state"].fillna(df["node_resource"])
        ).drop(
            columns=["node_resource", "node_karpenter_state"]
        )

        df_merged = df_merged.sort_values(["namespace", "pod", "timestamp"])

        nodepool_missing = df_merged["nodepool"].isna() | df_merged["nodepool"].eq("unallocated")
        if nodepool_missing.any():
            df_merged.loc[nodepool_missing, "nodepool"] = pd.NA
            df_merged["nodepool"] = (
                df_merged.groupby(["namespace", "pod"])["nodepool"]
                .transform(lambda values: values.ffill().bfill())
            )
            inferred_count = int((nodepool_missing & df_merged["nodepool"].notna()).sum())
            if inferred_count:
                self.log(f"[INFO] Inferred nodepool for {inferred_count} rows from another occurrence of the same pod.")

        df_merged["node"] = df_merged["node"].fillna("unallocated")
        df_merged["instance_type"] = df_merged["instance_type"].fillna("unallocated")
        df_merged["nodepool"] = df_merged["nodepool"].fillna("unallocated")
        df_merged["phase"] = df_merged["phase"].fillna("Pending")

        cols_to_fill = ["resource_kind", "resource", "value", "node", "instance_type", "nodepool", "phase"]
        df_merged[cols_to_fill] = (
            df_merged.groupby(["namespace", "pod"])[cols_to_fill]
            .ffill()
            .bfill()
        )

        df_merged = df_merged.drop_duplicates()

        df_merged = df_merged.groupby(
            ["timestamp", "pod", "namespace", "instance_type", "nodepool", "node", "resource_kind", "resource"],
            as_index=False
        ).agg({"value": "sum"})

        df_merged["metric"] = df_merged["resource"] + "_" + df_merged["resource_kind"]
        df_pivoted = df_merged.pivot(
            index=["timestamp", "pod", "namespace", "instance_type", "nodepool", "node"],
            columns="metric",
            values="value"
        ).reset_index()

        for col in ["cpu_request", "memory_request", "cpu_limit", "memory_limit"]:
            if col not in df_pivoted.columns:
                df_pivoted[col] = float("nan")
            else:
                df_pivoted[col] = pd.to_numeric(df_pivoted[col], errors="coerce")

        self.df_final = df_pivoted[df_pivoted["cpu_request"].notna() & df_pivoted["memory_request"].notna()]

        total_pods = self.df_final['pod'].nunique()
        self.log(f"[INFO] Number of pods after remove NAs and pods that finish on first timestamp: {total_pods}")

    def merge_pods_resources_with_pod_owner(self):
        self.df_final = pd.merge(self.df_final, self.kube_pod_owner, on=['namespace', 'pod'], how='left')
        self.df_final.rename(columns={'owner_name': 'replicaset'}, inplace=True)

    def merge_pods_resources_with_replicaset_owner(self):
        df_merged = pd.merge(self.df_final, self.kube_replicaset_owner, on=['namespace', 'replicaset'], how='left')

        df_merged['owner_kind'] = df_merged['owner_kind_y'].combine_first(df_merged['owner_kind_x'])
        df_merged['replicaset'] = df_merged['owner_name'].combine_first(df_merged['replicaset'])

        self.df_final = df_merged.drop(columns=['owner_kind_x', 'owner_kind_y'])

    def remove_not_considered_resources_and_namespaces(self):
        self.log("[INFO] Removing not considered resources and namespaces.")
        self.df_final = self.df_final[~self.df_final['namespace'].isin(['kube-system', 'monitoring'])]
        self.df_final = self.df_final[~self.df_final['owner_kind'].isin(['DaemonSet', 'Job'])]

    def build_container_usage_df(self):
        """
        Builds workload usage dataframe from raw container CPU and memory metrics.
        CPU is converted from cumulative counter to rate, aggregated pod -> workload.
        Memory is aggregated as instantaneous usage, pod -> workload.
        """
        self.log("[INFO] Building workload usage dataframe from raw container metrics.")

        cpu_df = self.container_cpu_usage_seconds_total.copy()
        cpu_df = cpu_df[
            cpu_df["pod"].notna() & cpu_df["pod"].ne("") &
            cpu_df["container"].notna() & cpu_df["container"].ne("")
        ]
        cpu_df["value"] = pd.to_numeric(cpu_df["value"], errors="coerce")
        cpu_df = (
            cpu_df
            .groupby(["namespace", "pod", "container", "timestamp"], as_index=False)
            .agg(value=("value", "max"))
            .sort_values(["namespace", "pod", "container", "timestamp"])
        )
        cpu_df["delta_value"] = cpu_df.groupby(["namespace", "pod", "container"])["value"].diff()
        cpu_df["delta_time"] = cpu_df.groupby(["namespace", "pod", "container"])["timestamp"].diff()
        cpu_df["cpu_usage"] = float("nan")
        valid_cpu = (
            cpu_df["delta_value"].notna() &
            cpu_df["delta_time"].notna() &
            cpu_df["delta_time"].gt(0) &
            cpu_df["delta_value"].ge(0)
        )
        cpu_df.loc[valid_cpu, "cpu_usage"] = (
            cpu_df.loc[valid_cpu, "delta_value"] / cpu_df.loc[valid_cpu, "delta_time"]
        )
        cpu_df = (
            cpu_df
            .groupby(["timestamp", "namespace", "pod"], as_index=False)[["cpu_usage"]]
            .sum(min_count=1)
        )

        mem_df = self.container_memory_usage_bytes.copy()
        mem_df = mem_df[
            mem_df["pod"].notna() & mem_df["pod"].ne("") &
            mem_df["container"].notna() & mem_df["container"].ne("")
        ]
        mem_df["value"] = pd.to_numeric(mem_df["value"], errors="coerce")
        mem_df = (
            mem_df
            .groupby(["namespace", "pod", "container", "timestamp"], as_index=False)
            .agg(memory_usage=("value", "max"))
        )
        mem_df = (
            mem_df
            .groupby(["timestamp", "namespace", "pod"], as_index=False)[["memory_usage"]]
            .sum(min_count=1)
        )

        usage_df = pd.merge(cpu_df, mem_df, on=["timestamp", "namespace", "pod"], how="outer").sort_values(["namespace", "pod", "timestamp"])

        usage_df = pd.merge(
            usage_df,
            self.kube_pod_owner[['namespace', 'pod', 'owner_name']],
            on=['namespace', 'pod'],
            how='left'
        ).rename(columns={'owner_name': 'replicaset'})

        usage_df = pd.merge(
            usage_df,
            self.kube_replicaset_owner[['namespace', 'replicaset', 'owner_name']],
            on=['namespace', 'replicaset'],
            how='left'
        )

        usage_df["name"] = usage_df["owner_name"].combine_first(usage_df["replicaset"])
        usage_df = usage_df.drop(columns=['owner_name'])

        usage_df = usage_df.sort_values(["namespace", "name", "pod", "timestamp"])
        usage_df[["cpu_usage", "memory_usage"]] = (
            usage_df
            .groupby(["namespace", "name", "pod"])[["cpu_usage", "memory_usage"]]
            .bfill()
        )

        usage_df = usage_df.dropna(subset=["cpu_usage"], how="all")
        usage_df = usage_df.dropna(subset=["memory_usage"], how="all")

        self.df_container_usage = usage_df
        self.log("[INFO] Workload usage dataframe built.")

    def process_hpa_target_metrics(self, spec_target_metric: pd.DataFrame) -> pd.DataFrame:
        resources = ("cpu", "memory")
        df = spec_target_metric.loc[spec_target_metric["metric_name"].isin(resources)]

        utilization_mask = df["metric_target_type"].astype(str).str.lower().eq("utilization")
        df.loc[utilization_mask, "value"] = pd.to_numeric(df.loc[utilization_mask, "value"], errors="coerce").clip(0, 100)

        keys = ["timestamp", "horizontalpodautoscaler", "namespace"]
        values = (
            df.pivot_table(index=keys, columns="metric_name", values="value", aggfunc="max")
            .reindex(columns=resources)
            .reset_index()
        )
        types = (
            df.pivot_table(index=keys, columns="metric_name", values="metric_target_type", aggfunc="first")
            .reindex(columns=resources)
            .reset_index()
            .rename(columns={"cpu": "cpu_type", "memory": "memory_type"})
        )
        return values.merge(types, on=keys, how="outer")

    def _build_segments(self, df: pd.DataFrame, id_cols: list, metric_cols: list) -> pd.Series:
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

    def build_hpa_metrics(self, spec_max_replicas, spec_min_replicas, spec_target_metric_wide):
        join_keys = ["timestamp", "horizontalpodautoscaler", "namespace"]
        id_cols = ["namespace", "horizontalpodautoscaler"]
        metric_cols = ["max_replicas", "min_replicas", "cpu", "memory", "cpu_type", "memory_type"]

        hpa_metrics = (
            spec_max_replicas.merge(spec_min_replicas, on=join_keys, how="outer")
            .merge(spec_target_metric_wide, on=join_keys, how="outer")
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
                "timestamp", "horizontalpodautoscaler", "namespace",
                "max_replicas", "min_replicas", "cpu", "memory",
                "cpu_type", "memory_type", "action",
            ])
            return

        hpa_metrics = hpa_metrics.sort_values(["namespace", "horizontalpodautoscaler", "timestamp"]).reset_index(drop=True)

        apply_action = hpa_metrics.copy()
        apply_action["action"] = "apply"

        delete_rows = hpa_metrics.groupby(["namespace", "horizontalpodautoscaler"], as_index=False).tail(1).copy()
        delete_rows["timestamp"] = delete_rows["last_timestamp"].apply(lambda x: min(int(x) + self.step, self.max_timestamp))
        delete_rows["action"] = "delete"

        self.df_hpa_trace = pd.concat([apply_action, delete_rows], ignore_index=True, sort=False)
        self.df_hpa_trace = self.df_hpa_trace.sort_values(["timestamp", "namespace", "horizontalpodautoscaler", "action"]).reset_index(drop=True)

    def process_and_save_pods_allocation(self):
        self.log("[INFO] Processing and saving pods allocation.")
        df_pods_allocation = self.df_final[self.df_final['timestamp'] == self.df_final['timestamp'].min()]

        df_pods_allocation = df_pods_allocation[
            ~df_pods_allocation["node"].isin(["unallocated"]) &
            ~df_pods_allocation["instance_type"].isin(["unallocated"])
        ]

        node_timestamp_counts = self.df_final.groupby('node')['timestamp'].nunique()
        valid_nodes = node_timestamp_counts[node_timestamp_counts > 1].index
        df_pods_allocation = df_pods_allocation[df_pods_allocation['node'].isin(valid_nodes)]

        self.df_pods_allocation = df_pods_allocation.groupby(
            ['namespace', 'node', 'nodepool', 'replicaset', 'owner_kind', 'instance_type']
        ).agg(pods_count=('replicaset', 'count')).reset_index()

        self.df_pods_allocation.to_csv("/tmp/pods_allocation.csv", index=False)

    def process_and_save_infrastructure_objects(self):
        """
        Identifies node creation and deletion events from df_final based on first/last
        appearance of each (node, instance_type) pair.
        """
        self.log("[INFO] Processing and saving infrastructure objects.")

        infra = self.df_final[['timestamp', 'node', 'instance_type', 'nodepool']].drop_duplicates()
        infra = infra.sort_values(['node', 'instance_type', 'timestamp'])

        first_idx = infra.groupby(['node', 'instance_type']).head(1).index
        last_idx = infra.groupby(['node', 'instance_type']).tail(1).index

        infra['action'] = ''
        infra.loc[first_idx, 'action'] = 'create'
        infra.loc[last_idx, 'action'] = 'delete'

        infra = infra[infra['action'].isin(['create', 'delete'])]

        counts = infra.groupby(['node', 'instance_type'])['action'].count()
        valid_nodes = counts[counts > 1].index
        infra = infra.set_index(['node', 'instance_type']).loc[valid_nodes].reset_index()

        infra = infra[(infra['node'] != 'unallocated') & (infra['instance_type'] != 'unallocated')]

        self.df_infrastructure = infra.sort_values(['timestamp', 'action', 'instance_type', 'node'])

    def process_and_save_final_trace(self):
        self.log("[INFO] Processing and saving final trace.")

        # A deployment is a single K8s object — it can only belong to one nodepool.
        # Resolve conflicts (pods spread across nodepools) by taking the most frequent
        # nodepool per (namespace, replicaset) before grouping.
        nodepool_map = (
            self.df_final
            .groupby(['namespace', 'replicaset'])['nodepool']
            .agg(lambda x: x.mode().iloc[0] if not x.empty else 'unallocated')
            .reset_index(name='resolved_nodepool')
        )
        df_resolved = (
            self.df_final
            .drop(columns=['nodepool'])
            .merge(nodepool_map, on=['namespace', 'replicaset'], how='left')
            .rename(columns={'resolved_nodepool': 'nodepool'})
        )

        conflicting = (
            self.df_final.groupby(['namespace', 'replicaset'])['nodepool'].nunique()
        )
        conflicting = conflicting[conflicting > 1]
        if not conflicting.empty:
            self.log(f"[WARN] Deployments with pods in multiple nodepools (resolved to modal nodepool): {conflicting.index.tolist()}")

        df_adjusted = df_resolved.groupby(['timestamp', 'namespace', 'nodepool', 'replicaset', 'owner_kind']).agg(
            pods_count=('replicaset', 'count'),
            cpu_request=('cpu_request', 'mean'),
            memory_request=('memory_request', 'mean'),
            cpu_limit=('cpu_limit', 'mean'),
            memory_limit=('memory_limit', 'mean'),
        ).reset_index()

        df_adjusted = df_adjusted.rename(columns={'pods_count': 'pods'})

        df_adjusted['action'] = 'scale'
        first_occurrences = df_adjusted.groupby(['replicaset', 'nodepool', 'namespace']).head(1).index
        df_adjusted.loc[first_occurrences, 'action'] = 'create'
        last_occurrences = df_adjusted.groupby(['replicaset', 'nodepool', 'namespace']).tail(1).index
        df_adjusted.loc[last_occurrences, 'action'] = 'delete'

        df_adjusted['pods_changed'] = (
            df_adjusted.groupby(['namespace', 'nodepool', 'replicaset'])['pods']
            .diff()
            .fillna(1) != 0
        )

        self.df_final = df_adjusted[
            df_adjusted['pods_changed'] | df_adjusted['action'].isin(['create', 'delete'])
        ].drop(columns=['pods_changed'])

        self.df_final.to_csv('/tmp/final_trace.csv', index=False)

    def merge_applied_objects(self, *objects_maps):
        merged = {}
        for objects_map in objects_maps:
            for namespace, objects in objects_map.items():
                merged.setdefault(namespace, [])
                merged[namespace].extend(objects)
        return merged

    def generate_workload_objects(self):
        workload_objects = {
            'setup': {
                'applied_objects': {},
                'workload_actions': []
            },
            'emulation': []
        }

        timestamps = sorted(
            set(self.df_final['timestamp']) |
            set(self.df_container_usage['timestamp']) |
            set(self.df_hpa_trace['timestamp'])
        )

        first_timestamp = min(timestamps)

        for timestamp in timestamps:
            timestamp = int(timestamp)

            group_final = self.df_final[self.df_final['timestamp'] == timestamp]
            group_usage = self.df_container_usage[self.df_container_usage['timestamp'] == timestamp]
            group_hpa = self.df_hpa_trace[self.df_hpa_trace['timestamp'] == timestamp]

            applied_objects = {}
            deleted_objects = []
            workload_actions_scale = []

            if not group_final.empty:
                applied_objects, deleted_objects, workload_actions_scale = \
                    self.k8s_objects_generator.generate_deployments(group_final)

            applied_hpa_objects = {}
            deleted_hpa_objects = []

            if not group_hpa.empty:
                applied_hpa_objects, deleted_hpa_objects = self.k8s_objects_generator.generate_hpa(group_hpa)

            applied_objects = self.merge_applied_objects(applied_objects, applied_hpa_objects)
            deleted_objects = deleted_objects + deleted_hpa_objects

            workload_actions_usage = []
            if not group_usage.empty:
                workload_actions_usage = self.k8s_objects_generator.generate_usage_workload_action(group_usage)

            workload_actions = workload_actions_scale + workload_actions_usage

            if timestamp == first_timestamp:
                workload_objects['setup']['applied_objects'] = applied_objects
                workload_objects['setup']['workload_actions'] = workload_actions
            else:
                workload_objects['emulation'].append({
                    "timestamp": timestamp,
                    "applied_objects": applied_objects,
                    "deleted_objects": deleted_objects,
                    "workload_actions": workload_actions,
                })

        return workload_objects

    def generate_infrastructure_objects(self):
        """
        Generates NodeClaim objects for infrastructure setup and emulation events.
        Uses df_infrastructure to track create/delete events over time.
        """
        first_timestamp = self.df_infrastructure['timestamp'].min()
        infrastructure_objects = {'setup': [], 'emulation': []}

        with open(self.instance_types_path, encoding="utf-8") as f:
            instance_data = json.load(f)

        for timestamp, group in self.df_infrastructure.groupby('timestamp'):
            applied_objects = []
            deleted_objects = []

            for _, row in group.iterrows():
                instance_name = row['node']
                instance_type = row['instance_type']
                nodepool_name = row['nodepool']
                action = row['action']

                if action == 'delete':
                    deleted_objects.append(instance_name)
                else:
                    nodeclaim = self.k8s_objects_generator.generate_nodeclaim(instance_type, instance_data, nodepool_name)
                    if nodeclaim:
                        target_list = infrastructure_objects['setup'] if timestamp == first_timestamp else applied_objects
                        target_list.append(nodeclaim)

            infrastructure_objects['emulation'].append({
                "timestamp": int(timestamp),
                "applied_objects": applied_objects,
                "deleted_objects": deleted_objects,
            })

        return infrastructure_objects

    def process_and_save_workload_and_infrastructure_objects(self):
        self.log("[INFO] Processing and saving output objects.")
        workload_objects = self.generate_workload_objects()
        infrastructure_objects = self.generate_infrastructure_objects()

        with open('/tmp/workload_description.json', 'w', encoding="utf-8") as f:
            f.write(json.dumps(workload_objects, indent=4))

        with open('/tmp/infrastructure_description.json', 'w', encoding="utf-8") as f:
            f.write(json.dumps(infrastructure_objects, indent=4))

    def run(self):
        self.log("[INFO] Starting Tracer.")
        self.load_data()
        self.preprocess_dataframes()
        self.select_necessary_columns()
        self.merge_pods_state_with_resources()
        self.merge_pods_resources_with_pod_owner()
        self.merge_pods_resources_with_replicaset_owner()
        self.remove_not_considered_resources_and_namespaces()
        self.build_container_usage_df()
        self.build_hpa_trace()
        self.process_and_save_pods_allocation()
        self.process_and_save_infrastructure_objects()
        self.process_and_save_final_trace()
        self.process_and_save_workload_and_infrastructure_objects()
